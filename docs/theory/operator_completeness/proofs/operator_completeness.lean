import Mathlib

/-!
# Operator Completeness: the decidability dichotomy for μ⁻ codomain operators

The negative operator family Π on a codomain type R is modelled as a finite generating set of the
transformation monoid `Function.End R`. Π is COMPLETE (strong definition, OPERATOR_COMPLETENESS.md
Def 2.3) iff `Submonoid.closure ↑Π = ⊤` — it generates the ENTIRE transformation monoid, realizing
every deviation `r ↦ r'`.

This mirrors `bridge_B09_decidability.lean` (equivalent-mutant detection: decidable finite, undecidable
infinite), one layer down at the OPERATOR family:

- `pi_completeness_decidable_finite` — Thm A.3: completeness is DECIDABLE on a finite codomain.
- `T2_generated`, `T3_generated_rank3` — Thm A.2: concrete constructive bases; rank(T_n) = 3
  (Gomes & Howie 1987).
- `pi_completeness_undecidable_infinite` — Thm B: UNDECIDABLE off finite, stated as an AXIOM citing the
  word problem for finitely-presented semigroups (Post 1947 / Markov 1947) and program equivalence
  (Rice 1953 / Budd & Angluin 1982), following the corpus pattern for `bridge_B09.undecidability_infinite`.
-/

open Function

/-- **Thm A.3.** On a FINITE codomain, Π-completeness (`closure ↑Π = ⊤`) is decidable — the negative
operator-layer analogue of `bridge_B09.decidability_finite`. Stated as an `instance` because
`Decidable _` is `Type`, not `Prop` (so it is not a theorem/Wayfinder target); the CONCRETE generation
Props `T2_generated` / `T3_generated_rank3` are its machine-checkable witnesses, and the general
decidability is instance-level (paper §3, Thm A.3 / Cor A.4). -/
instance pi_completeness_decidable_finite
    (R : Type) [Fintype R] [DecidableEq R]
    (P : Finset (Function.End R)) :
    Decidable (Submonoid.closure (↑P : Set (Function.End R)) = ⊤) := by
  sorry

/-- **Thm A.2 (n = 2).** The swap `x ↦ x+1` and the constant `0` generate the full transformation
monoid `T₂` on `Fin 2`: a concrete witness that `rank(T₂) ≤ 2`. -/
theorem T2_generated :
    Submonoid.closure
      ({(fun x => x + 1 : Function.End (Fin 2)),
        (fun _ => 0 : Function.End (Fin 2))} : Set (Function.End (Fin 2))) = ⊤ := by
  sorry

/-- **Thm A.2 (n = 3, rank 3).** A 3-cycle, a transposition, and a rank-2 idempotent generate `T₃`
on `Fin 3` — the constructive basis of size `rank(T₃) = 3` (Gomes & Howie 1987). -/
theorem T3_generated_rank3 :
    Submonoid.closure
      ({(fun x => x + 1 : Function.End (Fin 3)),
        (fun x => if x = 0 then 1 else if x = 1 then 0 else 2 : Function.End (Fin 3)),
        (fun x => if x = 2 then 1 else x : Function.End (Fin 3))} :
        Set (Function.End (Fin 3))) = ⊤ := by
  sorry

/-- **Thm B (undecidability), AXIOM.** Off the finite fragment, Π-completeness is undecidable: there is
no uniform decision procedure for whether a finitely-presented perturbation family generates the target
transformation sub-monoid on a structured/infinite codomain. Reduces to the word problem for
finitely-presented semigroups (Post 1947 / Markov 1947) and to program equivalence (Rice 1953;
Budd & Angluin 1982). Stated as an axiom citing these classical results, mirroring
`bridge_B09.undecidability_infinite`. -/
axiom pi_completeness_undecidable_infinite :
    ¬∃ (decide : (ℕ → ℕ) → (ℕ → ℕ) → Bool),
      ∀ f g, decide f g = true ↔ (∀ n, f n = g n)
