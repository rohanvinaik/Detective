# Artifact — *What a Mutation Score Certifies*

Machine-checked Lean 4 / Mathlib development accompanying the paper. All results are in the
single file `adequacy_completeness.lean` (29 theorems, no `sorry`). The 2026-09-07 audit
rechecked all 29 declarations and their axiom footprints under the pinned toolchain.
The three new counterexamples concern unreachable surviving guards, insufficient pointwise
sub-footprint coverage, and vacuous scores for empty footprints. This does not mechanize the
computability reductions or the probability model in the companion prose.

## Reproduce

```bash
lake exe cache get      # fetch the pinned Mathlib build cache
lake build              # builds and checks every theorem
```

Or check the file directly and inspect the axiom footprint of any result:

```bash
lake env lean adequacy_completeness.lean          # compiles clean, 0 sorry
# then, e.g.:  #print axioms progComplete_characterization
```

Every theorem is `#print axioms`-clean, depending on at most
`[propext, Classical.choice, Quot.sound]` (`det_factors` and `detW_const` on none), with no
`sorryAx`.

## Pinned environment

- Toolchain: `leanprover/lean4:v4.28.0` (see `lean-toolchain`).
- Mathlib: `v4.28.0`, commit `8f9d9cff6bd7` — pinned in `lake-manifest.json`. `lake exe cache get`
  resolves the matching prebuilt cache so the artifact does not depend on Mathlib's moving `master`.

## Contents

| Result (paper) | Lean name |
|---|---|
| Prop. (reduction) | `progScore_iff_scoreAt` |
| Prop. (every subset is a footprint) | `mov_surjective`, `mov_image_univ` |
| Thm. 3.2 (finite) / over programs | `footprint_characterization` / `progComplete_characterization` |
| Thm. 4.3 (general) | `footprint_characterization_general` |
| Cor. (value-guard basis) | `absolute_iff_guards`, `progComplete_absolute_iff_guards` |
| Cor. (finite/infinite dichotomy) | `complete_univ_infinite`, `progComplete_univ_infinite` |
| Cor. (constants iff n=2) | `constants_iff_card_two` |
| Thm. 4.4 (ceiling) | `ceiling` |
| Prop. (coupling fails) / degenerate | `coupling_fails` / `coupling`, `progComplete_coupling` |
| Prop. (subsumption) / (factoring) | `subsumes_iff_subset` / `det_factors` |
| Thm. 8.1 (min certifying suite) | `certify_lb`, `certify_ub`, `certify_infinite` |
| §10 (beyond the exact oracle) | `DetW`, `detW_singleton_of_nonconstant`, `detW_const`, `pseudo_tested_iff` |
| Bridge | `realizable`, `progComplete_iff_complete` |
