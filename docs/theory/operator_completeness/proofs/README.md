# Artifact — *What a Mutation Regime Can Know About a Function*

Machine-checked Lean 4 / Mathlib development accompanying the paper. All results are in the
single file `adequacy_completeness.lean` (38 theorems, no `sorry`). `Audit.lean` pins each theorem's
axioms with `#guard_msgs`, so the default build fails on any deviation. Which paper claims are
mechanized, and which are proved only in the paper, is listed in `../THEOREM_LEDGER.md`; the
computability reductions of Theorem 5.2 and §10 are not mechanized.

## Reproduce

```bash
lake exe cache get      # fetch the pinned Mathlib build cache
lake build              # builds and checks every theorem, then runs the axiom audit
```

Or check the file directly and inspect the axiom footprint of any result:

```bash
lake env lean adequacy_completeness.lean          # compiles clean, 0 sorry
# then, e.g.:  #print axioms progComplete_characterization
```

Every theorem depends on at most `[propext, Classical.choice, Quot.sound]` (`det_factors` and
`detW_const` on none), with no `sorryAx`; `Audit.lean` checks this on every build.

## Pinned environment

- Toolchain: `leanprover/lean4:v4.28.0` (see `lean-toolchain`).
- Mathlib: `v4.28.0`, commit `8f9d9cff6bd7` — pinned in `lake-manifest.json`. `lake exe cache get`
  resolves the matching prebuilt cache so the artifact does not depend on Mathlib's moving `master`.

## Contents

Numbering follows `../KNOWABILITY.md`.

| Result (paper) | Lean name |
|---|---|
| Prop. 2.4 (operator = footprint, over programs) | `progScore_iff_scoreAt` |
| Remark 2.5 (every subset is a footprint) | `mov_surjective`, `mov_image_univ` |
| Remark 3.3 (composition shrinks footprints) | `composition_shrinks_footprint` |
| Thm. 3.2 (finite Π) / over programs | `footprint_characterization` / `progComplete_characterization` |
| Thm. 3.2b (general Π) | `footprint_characterization_general` |
| Cor. 4.1 (value-guard basis) | `absolute_iff_guards`, `progComplete_absolute_iff_guards` |
| Cor. 4.2 (finite/infinite dichotomy) | `complete_univ_infinite`, `progComplete_univ_infinite` |
| Cor. 4.3 (constants iff n = 2) | `constants_iff_card_two` |
| Example 4.4 (constants on three values) | `constants_insufficient_on_three` |
| Thm. 4.5 (ceiling) | `ceiling` |
| Prop. 5.1 (partial guards) | `partial_guards_reach` |
| Prop. 6.1 (coupling not entailed) / guard-family case | `coupling_fails` / `coupling`, `progComplete_coupling` |
| Prop. 7.1 (subsumption = containment) / Prop. 7.2 (detection factors) | `subsumes_iff_subset` / `det_factors` |
| §7 (one subsuming footprint is insufficient) | `one_subfootprint_is_insufficient` |
| Thm. 8.1 (min certifying suite) | `prog_certify_lb`, `prog_certify_ub`, `certify_infinite`; `certify_lb`, `certify_ub` |
| Prop. 9.3 (oracle-relative core) | `DetW`, `detW_singleton_of_nonconstant`, `detW_surjective`, `detW_const` |
| Prop. 9.3 (empty detection sets score vacuously) | `empty_footprints_score_without_observations` |
| Remark 9.3b (constants under a weak oracle) | `constants_omega_iff_card_two`, `constant_guards_omega_iff_card_two` |
| Prop. 9.4 (pseudo-testedness, mixed oracle) / narrow form | `pseudo_tested_mixed_iff` / `pseudo_tested_iff` |
| Prop. 9.4b (mixed ceiling) | `MixedScoreAt`, `mixed_ceiling` |
| §10 (a surviving guard need not be a coverage gap) | `surviving_guard_without_gap` |
| Bridge | `realizable`, `progComplete_iff_complete` |
