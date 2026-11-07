# Theorem ledger: *What a Mutation Regime Can Know About a Function*

Every numbered claim of `KNOWABILITY.md`, with exactly how it is established. Four statuses:

- **Mechanized**: the paper's statement is a Lean theorem in `proofs/adequacy_completeness.lean`.
- **Via lemmas**: mechanized through supporting lemmas; the paper's statement is a direct instantiation or
  assembly of checked theorems, but is not itself one Lean theorem.
- **Paper proof**: proved in the paper only.
- **Empirical**: an observation from the experiment in `experiment/`, not a theorem.

The axioms of every Lean theorem are pinned by `proofs/Audit.lean`, which is part of the default build: `lake
build` fails if any theorem depends on `sorryAx` or on any axiom beyond `propext`, `Classical.choice` and
`Quot.sound`. Lean 4 v4.28.0, Mathlib v4.28.0 (commit `8f9d9cff6bd7`).

| Paper | Claim | Status | Lean / artifact |
|---|---|---|---|
| Prop 2.4 | a program-level score is the footprint-level score at `(range f, f(T))` | Mechanized | `progScore_iff_scoreAt` |
| Remark 2.5 | every subset of `R` (with `|R| ≥ 2`) is some operator's footprint | Mechanized | `mov_surjective`, `mov_image_univ` |
| Remark 3.3 | composition can shrink a footprint off the reachable set | Mechanized | `composition_shrinks_footprint` |
| Thm 3.2 | finite `Π`: sufficient for `Γ` iff every target footprint is the union of the `Π`-footprints it contains | Mechanized | `footprint_characterization` (footprints), `progComplete_characterization` (programs and suites) |
| Thm 3.2b | arbitrary `Π`: the finite-avoidance characterization | Mechanized | `footprint_characterization_general` |
| Bridge | sufficiency over programs and suites = sufficiency over footprint families; every `(I, O)` is realized | Mechanized | `progComplete_iff_complete`, `realizable` |
| Cor 4.1 | the value guards are the minimal absolutely sufficient regime | Mechanized | `absolute_iff_guards`, `progComplete_absolute_iff_guards` |
| Cor 4.2 | no finite regime is absolutely sufficient on an infinite return type | Mechanized | `complete_univ_infinite`, `progComplete_univ_infinite` |
| Cor 4.3 | constants are absolutely sufficient iff `|R| = 2` | Mechanized | `constants_iff_card_two` |
| Example 4.4 | on three values, the constants all die while the guard on the unobserved value survives | Mechanized | `constants_insufficient_on_three`; also `checker/` |
| Thm 4.5 | an absolute score of one iff `O = I` | Mechanized | `ceiling` |
| Remark 4.6 | output operators cannot separate inputs with equal outputs | Paper proof | one line: `p(f(x₁)) = p(f(x₂))` when `f(x₁) = f(x₂)` |
| Prop 5.1 | partial guards on `G` reach exactly the targets with footprint inside `G` | Mechanized | `partial_guards_reach` |
| Thm 5.2 | reduction of sufficiency to finitely many containment tests | Via lemmas | the reduction is Thm 3.2 |
| Thm 5.2 (1)–(2) | polynomial time on value tables; decidable for Presburger-definable footprints | Paper proof | standard facts (linear scans; Presburger decidability) |
| Thm 5.2 (3) | undecidable for total computable operators | Paper proof | halting reduction, Appendix A |
| Prop 6.1 | coupling is not entailed for output mutation | Mechanized | `coupling_fails` |
| Prop 7.1 | uniform subsumption iff footprint containment | Mechanized | `subsumes_iff_subset` |
| §7 example | one subsuming footprint per target is not enough | Mechanized | `one_subfootprint_is_insufficient` |
| Prop 7.2 | the detection set factors through the footprint | Mechanized | `det_factors` (definitional) |
| Thm 8.1 | minimum certifying suite has `|f(D)|` tests; none if `f(D)` is infinite | Mechanized | `prog_certify_lb`, `prog_certify_ub` (builds the suite), `certify_infinite`; observed-set forms `certify_lb`, `certify_ub` |
| Remark 8.2 | `σ(f)` is the teaching dimension of `f` in `C_Π(f)` | Paper proof | identification of definitions |
| Prop 9.3 | the oracle-relative reduction; singleton detection sets need a nonconstant oracle; constant oracle is vacuous | Via lemmas | `detW_singleton_of_nonconstant`, `detW_surjective`, `detW_const`, `empty_footprints_score_without_observations`; the set-system theorems apply to `Det_ω` families unchanged |
| Remark 9.3b | for finite `R` and nonconstant `ω`, constants are absolutely `ω`-sufficient iff `|R| = 2` | Mechanized | `constants_omega_iff_card_two`, `constant_guards_omega_iff_card_two` |
| Prop 9.4 | mixed-oracle pseudo-testedness characterization | Mechanized | `pseudo_tested_mixed_iff`; narrow `ω`-non-equivalent form `pseudo_tested_iff` |
| Prop 9.4b | the mixed ceiling | Mechanized | `mixed_ceiling` |
| §9.5 | pseudo-testedness under a uniform constant; agreement with the Prop 9.4 prediction | Empirical | `experiment/` (pinned libraries, seeds, raw records) |
| §10 | a surviving guard need not be a coverage gap | Mechanized | `surviving_guard_without_gap` |
| §10 | deciding reachability of a Boolean output is undecidable | Paper proof | halting reduction in §10 |

Theorem 3.2's necessity proof is also executable: `checker/sufficiency.py` decides finite sufficiency and,
when it fails, returns the theorem's counterexample (a program and a suite), which `verify_certificate`
re-checks from the definitions alone.
