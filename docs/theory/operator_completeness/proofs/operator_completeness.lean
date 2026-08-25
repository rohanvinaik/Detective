import Mathlib

/-!
# Operator Completeness — index of the machine-checked proofs (no axioms, no `sorry`)

This file introduces **no declarations**: it is a documentation index. All machine-checked content of the
paper lives in three sibling files, each fully proven (no `sorry`) and `#print axioms`-clean
(`[propext, Classical.choice, Quot.sound]`, no `sorryAx`):

- `T2_generated.lean`            — Thm A.1 (n = 2): the swap and the constant `0` generate `T₂` on `Fin 2`.
- `T3_generated_rank3.lean`      — Thm A.1 (n = 3, rank 3): a 3-cycle, a transposition, and a rank-2
  idempotent generate all 27 maps of `T₃` on `Fin 3`.
- `pi_incomplete_infinite.lean`  — Thm B: on an infinite `R`, a finitely generated submonoid of
  `Function.End R` cannot be `⊤` (countable closure vs uncountable monoid).

The remaining results are **paper proofs, not formalized here** — and, deliberately, this file states them
as prose rather than as `sorry` declarations or axioms, so nothing unproven is introduced:

- **Thm A.2** (finite ABSOLUTE completeness, in P): the P-time algorithm of §3 (rank argument + Schreier–Sims
  on the permutation generators + a rank-`(n-1)` scan). Its statement would be
  `Decidable (Submonoid.closure (↑P : Set (Function.End R)) = ⊤)` for `[Fintype R] [DecidableEq R]` — decidable,
  but not formalized here.
- **Thm A.3** (finite RELATIVE completeness, PSPACE-complete): transformation-monoid membership (Kozen 1977).
- **Thm C** (relative undecidability): the direct `L_g` reduction — relative completeness *is* finitely-generated
  submonoid membership, undecidable by Mihailova 1958 / Lohrey–Steinberg 2008 (results not in Mathlib).

## Provenance note (why there is no axiom here)

An earlier version of this file carried an `axiom` asserting the undecidability of extensional equality of
`ℕ → ℕ` functions (`¬∃ decide : (ℕ → ℕ) → (ℕ → ℕ) → Bool, ∀ f g, decide f g = true ↔ ∀ n, f n = g n`).
**That axiom was inconsistent with Mathlib's classical foundations** and has been removed: under
`Classical.propDecidable`, `fun f g => decide (∀ n, f n = g n)` is exactly such a `Bool`-valued function
(via `decide_eq_true_iff`), so the negation the axiom asserted is provable and `False` follows from it. The
lesson is standard: undecidability in Lean must be stated relative to a computability model
(`Computable` / `Partrec`), never as the non-existence of a `Bool`-valued function. Thm C's undecidability is a
paper proof (§5); if it is ever formalized it will be against such a model, not as an axiom.
-/
