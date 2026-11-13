# Tasks

Every unchecked box is remaining work. A checked box records an accepted subset and names its commit.
Take the first unchecked task whose **deps** are checked. Each task gives: the repository, the files,
what to build, the pure decision to extract and pin (house style: named string codes, docstring tagged
`(KII §n, pure — pinned)`), the hand-written intent test (module docstring cites the KII section), the
acceptance line, and the theory it implements. `KII` = `docs/theory/knowability_ii/KNOWABILITY_II.md`;
`design` = `design.md` beside this file. Read `docs/theory/knowability_ii/CONSTRAINT_BLOCK.md` first.

**Standing commands (AGENTS.md).** `export PP=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker`.
Every `detective`, `pytest` and `python` call is `PYTHONPATH=$PP .venv/bin/...` from the repo's own
venv. Never a bare `python3`/`detective`. Prove resolution once per session. Before every edit:
`find_referencing_symbols` on the symbol. Before every commit: the full suite, then
`uvx ruff@0.16.7 format <pkg> tests`, `uvx ruff@0.16.7 check <pkg> tests`, `uvx ruff@0.16.7 format --check .`.
Converge output is read IN FULL from a log file, never tailed.

**Invariants every task keeps (CONSTRAINT_BLOCK).** `SCORED_DISPOSITIONS` unchanged · value-vs-run
precedence unchanged · nothing promoted by assertion · no new dependency · features default off ·
with them off, every verdict/certificate/golden/`--json` field byte-identical modulo new optional
absent fields (V5) · `dead_site`/`masked` never invite a flag · every κ is a bracket with an S-version.

**Dependency graph.** `0 → W1`; `0 → W2 → W3 → W4 → W5`; `0 → D1`; `0 → D2`; `D1,W3 → D3`;
`D1,D3,W3 → D4`; `D1,D2,D4 → D5`; `D2,D5 → D6`; `W4,D3 → D7`; `W2,D3 → D8`; `D3–D6 → D9`;
`D5,D7,D9 → D10`; `W1 → V1`; `D4 → V2,V6`; `D7 → V3`; `D5 → V4`; `D10 → V5`; `all → X`.

---

## 0. Ground (both repositories)

- [ ] 0.1 **Register the thesis in the reference manifest.** Detective · `docs/theory/REFERENCE_MANIFEST.yaml`.
  Add bundled-prior entries (role, `sections_cited`, `cited_by: [docs/theory/knowability_ii/KNOWABILITY_II.md]`)
  for `docs/theory/operator_completeness/KNOWABILITY.md`, `docs/theory/NEGATIVE_SPECIFICATION.md`,
  `docs/theory/COMMUNICATING_DETERMINISM.md`, with sha256 of the COMMITTED files (commit the pending
  operator_completeness edits first or hash the committed blob: `git show HEAD:<path> | shasum -a 256`).
  Add an external entry for `~/Projects/rohan-vinaik.github.io/papers/Core Documents/SIGNIFICANCE_WEIGHTING.md`
  under its own `root` (extend `external_root` handling if the script supports only one root; if not,
  record `verified: true` with the sha and the absolute path in `role`). Acceptance:
  `python docs/theory/check_reference_manifest.py` exits 0 or reports only the pre-existing warnings.
  **deps:** none.

- [ ] 0.2 **Pin the BOUNDARY gap against the live table.** Wesker · `tests/test_boundary_local_guards_intent.py`
  (new), `docs/local_guards_check.py` (copy of Detective's `docs/theory/knowability_ii/local_guards_check.py`).
  The test imports `Wesker.engine._BoundaryMutator`, builds the regime per original operator from
  `_alternatives(op())` (replacement classes → their symbol; `bool` replacements → `"True"`/`"False"`),
  computes local footprints over `{L,E,G}` exactly as the script does, and asserts the uncertified
  targets per operator. BEFORE W1 the expected table is the gap (`<`→`['!=']`, `>`→`['!=']`,
  `==`→`['<','<=','>','>=']`, `!=`→`['<','<=','>','>=']`, `<=`/`>=`→`[]`); the test is written so that
  W1 flips the expectation to all-empty by editing ONE dict in the test and the docstring records both
  states with their commits. Acceptance: the test passes against 2fbd029 with the gap expectation.
  Theory: KII Cor 3.3. **deps:** none.

- [ ] 0.3 **Wesker-side pointer document exists and is linked.** Wesker · `docs/KNOWABILITY_II_WESKER.md`
  (written with this change; verify it is present and that `AGENTS.md` and `README.md` link it).
  Acceptance: `grep -n KNOWABILITY_II AGENTS.md README.md` finds both. **deps:** none.

---

## W1. BOUNDARY completeness repair (Wesker) — universe change, policy 10

- [ ] W1.1 **Add the missing guards to `_BoundaryMutator`.** Wesker · `Wesker/engine.py` class
  `_BoundaryMutator`. Add a fourth table `_FAR_SIDE: {ast.Lt: ast.NotEq, ast.Gt: ast.NotEq}` with
  dimension label `BOUNDARY:<Op>~far` ("the far side of the threshold is pinned"), appended in
  `_alternatives` after `_EQUALITY` and before the predicate constants. Add a fifth, TYPE-CONDITIONAL
  table `_ONE_SIDED: {ast.Eq: (ast.LtE, ast.GtE), ast.NotEq: (ast.Lt, ast.Gt)}` with labels
  `BOUNDARY:Eq~le` / `~ge` and `BOUNDARY:NotEq~lt` / `~gt`, generated ONLY when the comparison's operands
  are statically orderable (both sides are numeric literals, or names whose annotation is `int`/`float`,
  or arithmetic over those; implement `_orderable_operands(node) -> bool` as a pure decision beside
  `_statically_str`), so no mutant can raise `TypeError` on an unorderable operand (NS Def 7.3: a raise
  would be a crash kill, not `undefined`). Update `_count_boundary_target` through the same
  `_alternatives` (single source of truth — assert in a test that count and visit order agree, as the
  class docstring promises). Theory: KII Cor 3.2, 3.3. **deps:** 0.2.

- [ ] W1.2 **Policy and labels.** Wesker · `Wesker/policy.py`: `POLICY_VERSION = 10`;
  `_boundary_alternative_labels` picks up the new labels automatically (verify); `_fingerprint_counts`
  changes. `CHANGELOG.md` "Unreleased": one paragraph — the universe changed (BOUNDARY gains `~far` for
  `<`/`>` and type-conditional one-sided guards for `==`/`!=`), WHY (KII Cor 3.3, with the separating
  suite in one sentence), and that the id moved. **deps:** W1.1.

- [ ] W1.3 **DOF count per ordering comparison is a theorem, and the report says it.** Wesker ·
  `Wesker/engine.py` `dof_universe` / the dimension recorder. Under DOF mode, record the three local
  guards (`~shift`/`~far`/`False` for `<`, by Cor 3.2) as the dimensions of an ordering comparison and
  mark `~dir`, `~eq`, `True` as `subsumed_by: [...]` in the survivor/killed record (a new optional key
  `"subsumed_by"`), so exhaustive mode still runs them and DOF mode counts 3 questions per ordering
  comparison, not 5. README's headline counts (`2,795 questions`) will move; W5 re-measures. Pure
  decision: `boundary_dimension_role(label) -> "guard" | "subsumed"` `(KII Cor 3.2, pure — pinned)`.
  **deps:** W1.1.

- [ ] W1.4 **Flip 0.2's expectation and add the separating-suite fixture.** Wesker ·
  `tests/test_boundary_local_guards_intent.py`: expectation → all-empty; new
  `tests/test_boundary_far_side_intent.py`: a fixture module with `def below(a, b): return a < b` and a
  suite `{(1,2), (2,2)}`; run `run_function_profiling` with the policy; assert every pre-W1 BOUNDARY
  mutant is killed and the `~far` mutant SURVIVES (this is prediction P1 made executable). Acceptance:
  both tests pass; `local_guards_check.py` check 2 is updated to the repaired table and still exits 0
  (update `WESKER_*` dicts and `expected_gap` to the new state; keep the old state in a comment with the
  commit). **deps:** W1.1–W1.3.

- [ ] W1.5 **Detective consumes policy 10.** Detective · wherever `policy_id` is compared (receipts,
  `verify-rewrite`, certificates): no code change expected; run the suite and `detective receipt` on one
  function to confirm an old receipt reads as a policy mismatch with its existing sign, not a crash.
  **deps:** W1.2.

---

## W2. Site trace: reached / infected / propagated per test (Wesker)

- [ ] W2.1 **Site identity.** Wesker · `Wesker/engine.py` `_BaseMutator._mark_applied`: also record
  `self.site_id = f"L{lineno}:{type(node).__name__}:{ordinal}"` where `ordinal` counts fire-site nodes of
  that type on that line in traversal order (so two comparisons on one line are distinct). Carry it on
  `Mutant` as `site_id: str = ""` (optional, excluded from nothing: it is part of the record, not the id).
  **deps:** 0.

- [ ] W2.2 **Reach per survivor from existing trace evidence.** Wesker · `Wesker/engine.py`
  `run_function_profiling` after the kill loop: for each mutant with `mutated_line`, `reached` = the
  `test_id`s of `trace_evidence` entries that are admissible and whose `lines` contain `mutated_line`
  (the proof view, `admissible_line_coverage`, not the observed view — a cut trace must not count as
  reach). Emit as `site.reached` / `site.n_reached` on the record (design §2.1). This uses no new
  instrumentation. **deps:** W2.1.

- [ ] W2.3 **Infection probe (opt-in).** Wesker · `Wesker/engine.py` + new `Wesker/site_probe.py`.
  `run_function_profiling(..., site_trace: bool = False)`. When True: (a) compile an instrumented
  ORIGINAL in which every fire-site expression that any generated mutant targets is wrapped
  `__wesker_site__(<expr>, "<site_id>")`; run each covering test once more against it under the same
  live session to record, per test, the ordered list of (site_id, observation) — `observation` =
  `repr(v)[:200]` if `repr` succeeds else `type(v).__name__`; (b) for each mutant, compile the mutant with
  the SAME wrapping at its own site and run only the tests in `site.reached`; `infected` = tests whose
  observation list at that site differs from the original's. `propagated` = `infected ∩ killed_by_tests`
  (full-matrix) or `infected ∩ {test_name}` (first-killer; then also mark `"partial": true`). Emit the
  `site` block. The probe must be semantics-preserving: it returns its argument unchanged, never copies,
  never calls `__eq__`. Test: a fixture whose comparison is reached by 3 tests, infected by 1, propagated
  by 0 (a masked example: `x = a < b; x = True; return x`) yields `n_reached=3, n_infected=1, n_propagated=0`.
  **deps:** W2.1, W2.2.

- [ ] W2.4 **Verdict invariance.** Wesker · `tests/test_site_trace_invariance_intent.py`: on three
  fixture functions, `run_function_profiling(site_trace=False)` and `(site_trace=True)` agree on
  `killed`, `killed_by`, `mutant_disposition` and every count for every mutant; the only differences are
  the presence of `site` blocks. This is V5's Wesker half, pinned early. **deps:** W2.3.

---

## W3. Constraint emission (Wesker)

- [ ] W3.1 **`Wesker/constraints.py`.** New module per design §2.2: `Formula`, `formula_kind` (pure —
  pinned; truth-table test over ~20 expressions), `inline_bindings` (single-assignment names on the AST
  path from the function entry to the site; a name assigned twice, or inside a loop, is left as a
  variable and the formula is `opaque`), `reach_formula` (conjunction of path guards with polarity:
  `if`/`elif` bodies, `else` as negation of the chain, `while` bodies, `assert`; a guard outside the
  grammar ⇒ `opaque_guards += 1` and the formula keeps the renderable conjuncts, so partial information
  is kept, never dropped). **deps:** W2.1.

- [ ] W3.2 **The infect table.** Wesker · `Wesker/constraints.py` `INFECT_TABLE` keyed by
  `(category, original, replacement)`, each value a function `(left_src, right_src) -> str`. Rows:
  BOUNDARY all 7×6 pairs from the local footprints (`<`→`<=`: `a == b`; `<`→`>`: `a != b`; `<`→`==`:
  `a != b and not (a > b)`… derive each from the footprint regions: L ⇒ `a < b`, E ⇒ `a == b`, G ⇒ `a > b`,
  union ⇒ `or`); ARITHMETIC (`+`→`-`: `b != 0`; `-`→`+`: `b != 0`; `*`→`+`: `a*b != a+b`; `*`→`/`:
  `b*b != 1` style, write them out; `//`→`/`: `a % b != 0`; unary `-`: `a != 0`); LOGICAL (`and`→`or`:
  `bool(a) != bool(b)`; drop `not`: `True`); VALUE: `True`; DATAFLOW `x`→`y`: `x != y`; SWAP (i,j):
  `arg_i != arg_j`; OUTPUT: `True`; STATE/STMT/EXCEPTION/TYPE: `opaque`. Intent test: one assertion per
  row, each checked by evaluating both sides on a small grid (the formula is true exactly where the
  original and mutant local values differ). Theory: KII Def 4.1, Cor 3.2. **deps:** W3.1.

- [ ] W3.3 **Attach to records.** Wesker · `run_function_profiling`: for every mutant with a `site_id`,
  emit `constraint: {reach, infect, bindings}` on its survivor/killed record (design §2.1). Always on
  (static, cheap, no execution). Test: the shipping example from Detective's README yields, for the
  `net > threshold`→`>=` mutant, `reach.text == "True"` (no enclosing guard) and
  `infect.text == "subtotal - discount == threshold"` after inlining. **deps:** W3.2.

---

## W4. Surprise counts (Wesker)

- [ ] W4.1 **Measured base.** Wesker · `Wesker/engine.py` after the kill loop under `site_trace=True`:
  `q_fn` = (number of (mutant, test) pairs with test ∈ infected and test ∈ propagated) / (number of pairs
  with test ∈ infected), over ALL mutants of the function; `None` when the denominator is 0. Pure
  decision: `surprise_base(pairs_infected, pairs_propagated) -> "measured" | "unmeasured"` `(KII Def 7.4,
  pure — pinned)`. **deps:** W2.3.

- [ ] W4.2 **Per-survivor block.** Wesker · for each survivor with `n_infected > 0 and n_propagated == 0`
  emit `surprise: {n, q_floor, q_ceiling, bits_floor, bits_ceiling, base}` with `bits = -n*log2(1-q)` when
  `0 < q < 1`; `q == 1` ⇒ `bits = inf` rendered as `"inf"`; `base == "unmeasured"` ⇒ bits `null`
  (CONSTRAINT 7: never 0). `q_ceiling` is read from a prior `.wesker/mutation_report.json` `q_repo` if
  present else `null`. Test: the masked fixture from W2.3 with one other killed mutant gives
  `q_floor == 1.0`, bits `"inf"`; a function with no killed infected pair gives `base == "unmeasured"`.
  **deps:** W4.1.

---

## W5. Report schema and re-measurement (Wesker)

- [ ] W5.1 **Schema.** Wesker · `Wesker/metrics.py` `mutation_report.json`: add `"schema": 2`, `"q_repo"`
  (the repo-wide q over all functions measured with site trace, else `null`), and pass the per-record
  `site`/`constraint`/`surprise`/`subsumed_by` blocks through unchanged. `docs/usage.md`: a section
  "Site trace and constraints" with the JSON shape and the opt-in flag (`--site-trace` on the CLI,
  `site_trace=True` in the library API). **deps:** W2–W4.

- [ ] W5.2 **Re-measure the README's headline.** Wesker · run the README's Detective measurement under
  policy 10 DOF mode and update the three numbers (`the questions`, `Wesker DOF`, `per dim`) and the
  sentence about `1.00 mutants per behavioral dimension`; record the before/after in `CHANGELOG.md` with
  the command used. Do NOT tune anything to recover the old number. **deps:** W1.3, W5.1.

---

## D1. The solver (Detective)

- [ ] D1.1 **`Detective/entail.py`.** Per design §2.3. Grammar: parse `Formula.text` with `ast`;
  accept Name, Constant (int/float/bool/str), UnaryOp(Not/USub), BinOp(+,-,*,//,%,** with int Constant
  exponent), Compare (chained), BoolOp; anything else ⇒ `Opaque`. Evaluate with `Fraction` for numbers.
  `components`, `domain_for` (constants in the component ±1, `equivalence.boundary_probe_values`, and the
  bound as a cap on the product of domain sizes; when the product exceeds the bound, enumerate the
  first `bound` tuples in a fixed order and set `bound_hit`), `decide`, `decide_pair`. `Verdict` statuses
  are EXACTLY `ENTAILED | REFUTED | UNDETERMINED | INCONSISTENT`. `deciding` by greedy premise dropping.
  Standard library only. Design reference: TrialLedger `layer2/entail.py` (read it for the shape; do
  not import it). **deps:** 0.

- [ ] D1.2 **Intent tests.** Detective · `tests/test_entail_intent.py`: (a) `a < b` with premise
  `a >= b` ⇒ `REFUTED`, deciding = that premise; (b) with `a > 5` and `a < 3` ⇒ `INCONSISTENT`;
  (c) `a*b == a+b` over ints bound 50 ⇒ `UNDETERMINED` with a witness `(2,2)` and `bound_hit False`;
  (d) a polynomial over 3 vars with bound 10 ⇒ `bound_hit True`; (e) an opaque conjunct ⇒ blocker named,
  status `UNDETERMINED`; (f) two formulas sharing no variable are separate components and a contradiction
  in one does not change the other's verdict (TrialLedger's rule: a contradiction anywhere in the
  COMPONENT is INCONSISTENT for that component only — decide and document which; KII Def 4.4 follows
  TrialLedger: the query's component). **deps:** D1.1.

---

## D2. The premise ledger (Detective)

- [ ] D2.1 **`Detective/premises.py`.** Per design §2.4: `Premise`, `premise_admission` (pure — pinned,
  truth-table intent test over origin × spine_confirmed × retains_plurality × user_confirmed),
  `s_version`, `in_scope`, `load/save` through `atomic_store.read_json_store` / `write_json_store` at
  `.detective/premises.json`. The store is user data (like `inputs.json`): never purged by `purge`
  without `--yes`; document in `AGENTS.md`'s "Between runs" list. **deps:** 0.

- [ ] D2.2 **`flag` and `--fence` write premises.** Detective · `Detective/cli.py` flag handler and
  `Detective/equivalents.py`: on `add_flag` also write the corresponding premise (origin `author`,
  status `confirmed`, source `flag:<key>`); on `--fence`, `forbidden(...)`. The flag store stays the
  authority for the flag's own verdict (`flag_verdict`); the premise is the ledger's view. Test: flagging
  writes one premise; re-flagging is idempotent (same id). **deps:** D2.1.

- [ ] D2.3 **`detective premises` verb.** Detective · `cli.py`: `premises list [file::fn]` (table: id,
  scope, origin, status, source, created), `premises adopt <id>`, `premises reject <id>`,
  `premises propose "<formula>" --scope function:<key> [--origin author|default]`. Adopting a `corpus`
  premise requires `premise_admission` ⇒ `"confirmed"` (spine + plurality + the user's adoption), else
  prints the inadmissibility reason and changes nothing. Add to `_STATIC_COMMANDS`; exit codes: `0`
  listed/changed, `1` inadmissible (a measured refusal), `2` malformed formula. **deps:** D2.1.

---

## D3. The survivor state (Detective)

- [ ] D3.1 **`survivor_state`, `survivor_region`, `survivor_remedy`.** Detective ·
  `Detective/equivalence.py`, beside `residual_disposition` (unchanged). Signatures and precedence per
  design §2.5. `survivor_remedy` returns the printed remedy string per code (the table in KII §5).
  **deps:** D1, W3 (for the verdict inputs; the decision itself is pure and testable without them).

- [ ] D3.2 **Feed it.** Detective · `Detective/engine.py` around the `classify_survivor` call (≈ line
  3637) and `Detective/converge.py` where `survivor_records` are read (≈ lines 319–326): for each
  survivor record with a `constraint` block, build `Formula`s, load premises in scope, call
  `entail.decide_pair`, compute `violated_confirmed` (re-decide with confirmed premises removed: a witness
  appears ⇒ True), read `site.n_infected/n_propagated` and `surprise` when present (else 0 / False), and
  call `survivor_state`. Store the code on `MutantVerdict` as `state: str = ""` (optional) and the
  `Verdict`s as `reach_verdict` / `pair_verdict` (optional). With no `constraint` block, `state` is
  `residual_disposition`'s code (backward compatible). **deps:** D3.1.

- [ ] D3.3 **Injectivity intent test.** Detective · `tests/test_survivor_state_intent.py`: enumerate the
  KII §5 table literally (one assertion per row, with the inputs that produce it); then assert that for
  every pair of codes with different `survivor_remedy`, the rendered sign prefixes (D3.5) differ; and
  that `dead_site` and `masked` remedies contain "fix the code" and never "flag". **deps:** D3.1.

- [ ] D3.4 **Consumption and distinction gates pass.** Detective · run `consumption.declared_decisions`
  / `distinction.consumer_reads` (the §3.2 checks): the three new decisions are consumed by production
  code, and every consumer distinguishes all their codes or names the ones it collapses and why (a
  renderer may collapse `value_residual`/`fixture_residual`/`structural_residual` into today's caveat
  path only by calling `residual_disposition`'s existing consumer). **deps:** D3.2, D3.5.

- [ ] D3.5 **Render the new signs.** Detective · `cli.py` `_format_survivor_report` and
  `_format_converge_terse`, and `candidate_equivalent_caveat` (consume `state` when present): new lines
  `dead site L<n>` · `local equivalent` (with the invariant when known) · `masked on N (q=…, bits …)` ·
  `reachable if ¬<premise id>: <formula>` · `pseudo-tested (ω): <codomain>` · `open at B` ·
  `INCONSISTENT · premises {ids}`. The remedy line comes from `survivor_remedy`. `dead_site` and `masked`
  never render a `flag` suggestion (assert in D3.3). `--json`: `state`, `remedy`, `region`, verdicts.
  **deps:** D3.2.

---

## D4. Solver-directed witnesses and the DOF⁰ collapse (Detective)

- [ ] D4.1 **Band B4 — solver-directed input synthesis.** Detective · `Detective/engine.py` beside the
  B1 guard-directed retry (`_guard_directed_inputs` / `guard_comparison_target`): a new retry
  `_solver_directed_inputs(record, premises)` that takes `decide_pair`'s witness (a dict over parameter
  names) and renders it as an `L` tuple in parameter order (unassigned parameters take the existing grid
  default). It is a POSITIVE-ONLY retry: it can turn a candidate-equivalent into a KILL and never the
  reverse (NS Prop 6.5's ladder; the witness is executed through `classify_survivor`). Gate: the
  survivor's formulas are not opaque and the witness is expressible. Record `witness_source: "solver"`
  on the written test's docstring line (beside the existing `(equivalence search)`). **deps:** D1, D3, W3.

- [ ] D4.2 **DOF⁰ rule.** Detective · `Detective/equivalence.py`: `bears_on_intent(vars, premise_texts,
  fence_texts, intent_test_param_refs) -> bool` `(KII §5 rule 3, NS Thm 6.2, pure — pinned)`: True iff
  any confirmed premise/fence in scope mentions a variable in `vars`, or any hand-written intent test
  (origin census "intent") references that parameter by name in its body. When False and the pair is
  satisfiable, B4 runs WITHOUT asking (no `DO THIS --input`), and the written test is labelled
  `characterization — DOF⁰` in its docstring. When True, the survivor becomes `reachable_if` (if a
  confirmed premise is violated by every witness) or stays on the normal path. **deps:** D4.1, D2.

- [ ] D4.3 **`reachable_if` names its premise and its κ.** Detective · when `survivor_state` returns
  `reachable_if`, the record carries `violated_premise_id` and the rendered line reads
  `reachable if ¬<id> (<formula>) · κ [f, c] S <ver>` once D5 exists (until then, without κ). The
  `DO THIS` block for this state says: `premises list`, and the one imperative is to confirm or reject
  THAT premise — never to supply an `--input` that violates a confirmed premise. **deps:** D4.2.

---

## D5. κ, the ordered queue, d (Detective)

- [ ] D5.1 **`premise_kappa`.** Detective · `Detective/kappa.py` per design §2.6 (re-entail the
  candidate's component with it adopted; floor/ceiling; `s_version` stamped). Intent test: three
  survivors sharing `subtotal`, one not; the premise `subtotal >= 0` has floor 3; adopting it then
  re-computing gives floor 0 for a second premise that only re-covers the same three (antitone within a
  component, KII Prop 7.2). **deps:** D1, D2, D4.

- [ ] D5.2 **The teacher queue.** Detective · `rank_teacher_queue`: items are (a) `proposed` premises
  with their κ brackets, (b) `reachable_if` survivors' violated premises (re-ask), (c) `genuine_equivalent`
  survivors (flag questions, κ floor 1), (d) `pseudo_tested_oracle` survivors; ordered floor desc,
  ceiling desc, surprise desc; stop marker where floor == 1 ("tail: each of these is its own question").
  **deps:** D5.1.

- [ ] D5.3 **`d` at the quotient.** Detective · `measure_d(adopted, call_graph)` using `kappa.is_bridge`
  on `build_call_graph(project_root)`; report `d` in `detective censor` and in the five-number line when
  non-zero. **deps:** D5.1.

---

## D6. Corpus candidates as proposed premises (Detective)

- [ ] D6.1 **Censors write proposed premises.** Detective · `Detective/censor.py` /
  `promotion_ledger.py`: every harvested `Censor` (call-site absence; rejected rewrite) also writes a
  `Premise(origin="corpus", status="proposed", source=<spine>)` whose `formula_text` is the censor's
  region rendered in `L` (e.g. `arg0 is not None`, `arg0 >= 0` from an observed-range near-miss); a
  censor whose region is not renderable in `L` writes no premise and says so in `censor` output
  (`not expressible as a premise`). `censor_admissible` and `premise_admission` must agree — one calls
  the other; add a test that they cannot drift. The promotion loop stays OFF (NS §16 discipline).
  **deps:** D2, D5.

- [ ] D6.2 **`censor` prints κ brackets.** Detective · `cli.py` censor handler: each candidate row gains
  `κ [floor, ceiling] · S <ver> · <admissible|proposed|inadmissible: reason>`. A candidate confirmed only
  by the engine's own derivations prints `inadmissible: self-confirmed` (CONSTRAINT: never a low κ).
  **deps:** D6.1.

---

## D7. Surprise rendering and the absent-expected-kill rule (Detective)

- [ ] D7.1 **`masked_disposition`.** Detective · `Detective/equivalence.py`:
  `masked_disposition(n_infected, n_propagated, base, bits_floor, knee_bits) -> "masked" | "not_masked" |
  "unmeasured"` `(KII Def 7.4, Prop 7.5, pure — pinned)`: `unmeasured` when `base != "measured"`;
  `masked` when `n_infected > 0 and n_propagated == 0 and bits_floor >= knee_bits`; the knee is the
  function's own bulk/tail knee computed as the median `bits_floor` over its masked candidates (one
  candidate ⇒ knee = its own bits, i.e. masked). Document that the knee is a first choice (KII §13 item 3).
  **deps:** W4, D3.

- [ ] D7.2 **Route to code.** Detective · the `DO THIS` block for a `masked` survivor names the line and
  the deleted/overwritten value (`the value of <expr> at L<n> is computed on N executions and never
  reaches the return`), suggests `decompose` or a code edit, and never `flag`. `audit --check`: a
  `masked` survivor is a measured gap (exit 1), not a modulo-equivalent. **deps:** D7.1.

---

## D8. The negative twins (Detective, with Wesker where noted)

- [ ] D8.1 **State in the codomain (ω = projection).** Detective · for a method target, after converge
  observes receiver post-state (`equivalence._observe_receiver_state` / `state_witness_attrs`), scan the
  covering tests' source for attribute reads of the receiver's changed fields (`\.<field>\b` in the test
  body — an honest proxy, labelled `oracle-read proxy`); a STATE/STMT survivor whose only effect is on a
  field no covering test reads is `pseudo_tested_oracle` with codomain `state:<field>` and remedy
  "assert `<field>`, or fence it as not part of the contract". Theory: KII §8 row D, KP §9 Prop 9.4.
  **deps:** W2, D3.

- [ ] D8.2 **Exception oracle class.** Detective · for EXCEPTION survivors, classify the covering tests'
  oracle: `pytest.raises(<Specific>)` / `except <Specific>` ⇒ `specific`; `pytest.raises(Exception)`,
  bare `except`, `with pytest.raises(BaseException)` ⇒ `broad`. A `broad` oracle on a raised-type swap
  survivor ⇒ `pseudo_tested_oracle` with codomain `raise` (KP Prop 9.4b: the mixed score cannot reach one
  under a non-injective ω). Pure decision `exception_oracle_class(raises_targets: tuple[str, ...]) ->
  "specific" | "broad" | "none"`. **deps:** D3.

- [ ] D8.3 **Per-site output coverage (Prop 3.4).** Detective · under `--two-sign`, group OUTPUT Form-A
  survivors by return site (`mutated_line`), print `return L<n>: observed {…}` from the site trace's
  observations at that site, and `dead site L<n>` when a return site has `n_reached == 0` across all
  covering tests. **deps:** W2, D3.

- [ ] D8.4 **Streams.** Detective/Wesker · verify Form B's yield wrapper materializes a bounded prefix for
  the oracle (`mu_minus.perturb_yields`); if the observation is an address `repr`, render the survivor as
  `constant oracle (address repr) — materialize the stream` rather than `candidate-equivalent`. Pure
  decision `observation_is_address(repr_text) -> bool`. Theory: KII §8 row F, KP Prop 9.3. **deps:** D3.

---

## D9. The five-number report (Detective)

- [ ] D9.1 **Compute.** Detective · `Detective/converge.py` / `audit.py`: `information_report(states,
  regions, deciding_origins) -> dict` `(KII Def 6.3, pure — pinned)`: `H0` = total dimensions (as today's
  DOF total); `L` = value-killed + `dead_site` + `local_equivalent` + `masked` + DOF⁰-pinned;
  `L_ind` = survivors whose state would change under a `proposed` admissible corpus premise; `H_star`
  = `open_at_bound` + `genuine_equivalent` + `pseudo_tested_oracle` + `reachable_if`; `I_ext` = length
  of the teacher queue. Always carries `"basis": "coverage analog, not bits"` and `s_version`.
  **deps:** D3–D6.

- [ ] D9.2 **Print and persist.** Detective · one `info` line after the verdict line (design §2.7);
  `--json` field `information`; certificates and receipts record `s_version` and the five numbers at
  the time of the verdict; `verify-rewrite` compares `H0` before/after and names a change in `H0` as
  `dimensions changed` (KII Prop 6.4's visibility claim — the receipt makes a collapsed-output rewrite
  visible). **deps:** D9.1.

---

## D10. The surface (Detective)

- [ ] D10.1 **`detective ask file::fn`.** Detective · prints the ordered teacher queue (D5.2): one row per
  item — kind, the question in plain words (`is "subtotal >= 0" true for every caller?` /
  `does <field> belong to the contract?` / `is mutant <id> a rewording?`), κ bracket, surprise, S-version;
  a `tail` marker; exit `0` (advisory, never gates). Signposted like `plan`. **deps:** D5, D7, D9.

- [ ] D10.2 **`DO THIS` names the max-κ item.** Detective · `_converge_commands` / `_converge_decision`:
  when the queue is non-empty, the single imperative is to answer its head (`premises adopt <id>` /
  `premises reject <id>` / `flag …` / an assertion to add), with its bracket; the menu is `detective ask`.
  Pure decision `next_move_kind(queue_head_kind) -> str` consumed by the block. **deps:** D10.1.

- [ ] D10.3 **Vocabulary and documents.** Detective · `ARCHITECTURE.md` §0.1: add `premise`, `S-version`,
  `survivor state`, `κ bracket`, `surprise`, `masked`, `dead site`, `teacher queue`; §10: the solver's
  decidability rungs as known boundaries. `COMMUNICATING_DETERMINISM.md` §3.1: append the new collision
  rows (`candidate-equivalent — UNPROVEN` merged `dead_site` · `masked` · `local_equivalent` ·
  `reachable_if` · `genuine_equivalent`; `--input` merged `DOF⁰` · `teacher`) and §4: the four
  quantity rules (KII §9). `docs/theory/GLOSSARY.md`: the Knowability II section (written with this
  change; verify). `AGENTS.md`: the premise store in the "Between runs" list and a line on `ask`.
  **deps:** D10.2.

---

## V. Validation (the predictions of KII §11)

- [ ] V1 **P1 — BOUNDARY gap on a real suite.** Wesker · W1.4's fixture is the test; additionally run
  the repaired policy on one real repo function with a `<` guard whose suite tests only below-and-at
  (find one with `grep -n ' < ' | ` + its tests) and record whether `~far` survives. Record in
  `docs/dogfood/knowability_ii_P1.md`. **deps:** W1.

- [ ] V2 **P2 — the shipping example resolves with `I_ext = 0`.** Detective · run converge on the README's
  `shipping_fee` under D4 with no premises; expect `info … I_ext 0`. Record the full log. **deps:** D4, D9.

- [ ] V3 **P3 — masked survivors are dead stores.** Detective · run `audit --two-sign` with site trace
  over Detective's own pure decisions (the `(pure — pinned)` set, `consumption.declared_decisions`);
  classify every `masked` survivor by hand (dead store / unreachable branch / other) in
  `docs/dogfood/knowability_ii_P3.md`; report the fraction. **deps:** D7.

- [ ] V4 **P4, P5 — κ ordering and d.** Detective · on the dogfood set (`docs/dogfood/`), count teacher
  questions to `COMPLETE` with κ ordering versus flat order; measure `d` (D5.3). Record both.
  **deps:** D5, D10.

- [ ] V5 **Regression — features off, nothing moves.** Both · run the full suites and the dogfood
  converges with `site_trace=False` and no premises; diff every `--json` against the pre-change outputs
  (saved at the start of the change: `docs/dogfood/pre_knowability_ii/`): identical modulo new optional
  absent fields. This gate must pass before any release pairing. **deps:** all D and W.

- [ ] V6 **P6 — the solver finds what the grid misses.** Detective · on functions with a polynomial infect
  formula in ≥ 2 variables (grep the W3 records for `kind == "polynomial"`), compare survivor sets with
  B4 on and off; record each `candidate-equivalent → killer_ready` transition with its witness.
  **deps:** D4.

---

## X. Pointers, changelogs, release pairing

- [ ] X.1 **Pointers present.** Detective: `docs/theory/operator_completeness/README.md` (follow-up
  line), `docs/theory/GLOSSARY.md` (Knowability II section), `NEGATIVE_SPECIFICATION.md` §18 item 11,
  `AGENTS.md`, `ARCHITECTURE.md` §0 (one sentence). Wesker: `AGENTS.md`, `README.md` theory paragraph,
  `docs/KNOWABILITY_II_WESKER.md`. (Written with this change; verify each resolves.) **deps:** none.
- [ ] X.2 **CHANGELOGs.** Both · one entry per stage landed, newest first, naming the policy id movement
  (W1 only) and the schema version (W5). **deps:** each stage.
- [ ] X.3 **Release pairing.** Both · Detective's Wesker floor rises to the Wesker release that carries
  W1–W5; the pair is published together per `RELEASE_1_2_x.md` precedent; nothing in this change is
  released before V5 passes. **deps:** V5.
