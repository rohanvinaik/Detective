import adequacy_completeness

/-!
# Axiom audit

Each block below states, as a checked expectation, exactly which axioms a theorem of
`adequacy_completeness.lean` depends on. `#guard_msgs` turns a mismatch into a build error, so
`lake build` fails if any theorem acquires `sorryAx` or any other axiom beyond Lean's three standard
ones (`propext`, `Classical.choice`, `Quot.sound`). Theorems are listed in file order.
-/

/-- info: 'footprint_characterization' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms footprint_characterization

/-- info: 'absolute_iff_guards' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms absolute_iff_guards

/-- info: 'ceiling' depends on axioms: [propext, Quot.sound] -/
#guard_msgs in
#print axioms ceiling

/-- info: 'coupling' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms coupling

/-- info: 'subsumes_iff_subset' depends on axioms: [propext, Quot.sound] -/
#guard_msgs in
#print axioms subsumes_iff_subset

/-- info: 'det_factors' does not depend on any axioms -/
#guard_msgs in
#print axioms det_factors

/-- info: 'constants_iff_card_two' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms constants_iff_card_two

/-- info: 'certify_lb' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms certify_lb

/-- info: 'certify_ub' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms certify_ub

/-- info: 'progScore_iff_scoreAt' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms progScore_iff_scoreAt

/-- info: 'realizable' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms realizable

/-- info: 'progComplete_iff_complete' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms progComplete_iff_complete

/-- info: 'progComplete_characterization' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms progComplete_characterization

/-- info: 'coupling_fails' depends on axioms: [propext, Quot.sound] -/
#guard_msgs in
#print axioms coupling_fails

/-- info: 'footprint_characterization_general' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms footprint_characterization_general

/-- info: 'detW_singleton_of_nonconstant' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms detW_singleton_of_nonconstant

/-- info: 'detW_const' does not depend on any axioms -/
#guard_msgs in
#print axioms detW_const

/-- info: 'pseudo_tested_iff' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms pseudo_tested_iff

/-- info: 'pseudo_tested_mixed_iff' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms pseudo_tested_mixed_iff

/-- info: 'mov_surjective' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms mov_surjective

/-- info: 'mov_image_univ' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms mov_image_univ

/-- info: 'progComplete_absolute_iff_guards' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms progComplete_absolute_iff_guards

/-- info: 'progComplete_coupling' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms progComplete_coupling

/-- info: 'complete_univ_infinite' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms complete_univ_infinite

/-- info: 'progComplete_univ_infinite' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms progComplete_univ_infinite

/-- info: 'certify_infinite' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms certify_infinite

/-- info: 'surviving_guard_without_gap' depends on axioms: [propext, Quot.sound] -/
#guard_msgs in
#print axioms surviving_guard_without_gap

/-- info: 'one_subfootprint_is_insufficient' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms one_subfootprint_is_insufficient

/-- info: 'empty_footprints_score_without_observations' depends on axioms: [propext, Quot.sound] -/
#guard_msgs in
#print axioms empty_footprints_score_without_observations

/-- info: 'prog_certify_ub' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms prog_certify_ub

/-- info: 'prog_certify_lb' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms prog_certify_lb

/-- info: 'mixed_ceiling' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms mixed_ceiling

/-- info: 'detW_surjective' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms detW_surjective

/-- info: 'constant_guards_omega_iff_card_two' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms constant_guards_omega_iff_card_two

/-- info: 'constants_omega_iff_card_two' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms constants_omega_iff_card_two

/-- info: 'constants_insufficient_on_three' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms constants_insufficient_on_three

/-- info: 'partial_guards_reach' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms partial_guards_reach

/-- info: 'composition_shrinks_footprint' depends on axioms: [propext] -/
#guard_msgs in
#print axioms composition_shrinks_footprint
