import Mathlib

/-!
# Operator Completeness — statements and one cited axiom (NOT the machine-checked proofs)

This umbrella file is **statements only**. The machine-checked content of the paper lives in the three
sibling files, each fully proven (no `sorry`) and `#print axioms`-clean:

- `T2_generated.lean`            — Thm A.1 (n = 2): swap + constant generate `T₂` on `Fin 2`.
- `T3_generated_rank3.lean`      — Thm A.1 (n = 3): 3-cycle + transposition + rank-2 idempotent generate `T₃`.
- `pi_incomplete_infinite.lean`  — Thm B: on an infinite `R`, a f.g. submonoid of `Function.End R` ≠ ⊤
  (countable closure vs uncountable monoid).

What this file adds is (a) the *signature* of the finite-decidability result, whose actual proof is the
polynomial-time algorithm in the paper (§3, Thm A.2) and is not formalized as a Lean term; and (b) **one
cited classical fact, recorded as an axiom** — the Rice-flavored ingredient behind the paper's *non-load-bearing*
Remark 5.2.

Honest scope, so nothing here is oversold:
- Thm A.1 (finite generation, n = 2,3): **proven** — in the T2/T3 sibling files, not here.
- Thm A.2 (finite ABSOLUTE completeness, in P): the `instance` below is a **signature stub**; the proof is the
  rank-argument + Schreier–Sims of paper §3, not a Lean term. It carries `sorry` deliberately.
- Thm A.3 (finite RELATIVE completeness, PSPACE-complete): transformation-monoid membership (Kozen 1977).
  A paper result, not formalized here.
- Thm B (infinite-absolute impossibility): **proven** in `pi_incomplete_infinite.lean` (elementary
  cardinality — a countable closure cannot equal the uncountable `Function.End R`).
- Thm C (relative undecidability): a **paper proof** (§5) by direct `L_g` reduction — relative completeness IS
  finitely-generated submonoid membership, undecidable by Mihailova 1958 / Lohrey–Steinberg 2008 (results not
  in Mathlib). It is **NOT** the axiom below and is not formalized here.
- The axiom `func_equality_undecidable` below is the classical undecidability of extensional equality of
  `ℕ → ℕ` functions — the Rice-flavored fact behind the paper's *non-load-bearing* Remark 5.2 (its connection to
  equivalent-mutant detection, Rice 1953 / Budd–Angluin 1982). It is an adjacent cited fact, **not** part of the
  proof of Thm C.
-/

open Function

/-- **Thm A.2 (signature stub).** On a FINITE codomain, absolute Π-completeness (`closure ↑Π = ⊤`) is
decidable. Recorded as an `instance` because `Decidable _` is `Type`, not `Prop`. The actual decision
procedure is the polynomial-time algorithm of paper §3, Thm A.2 (rank argument + Schreier–Sims on the
permutation generators + a rank-`(n-1)` scan) — it is **not** formalized as a Lean term here, hence the
deliberate `sorry`. The concrete generation witnesses `T2_generated` / `T3_generated_rank3` (sibling files)
are the machine-checked base cases. -/
instance pi_completeness_decidable_finite
    (R : Type) [Fintype R] [DecidableEq R]
    (P : Finset (Function.End R)) :
    Decidable (Submonoid.closure (↑P : Set (Function.End R)) = ⊤) := by
  sorry

/-- **Cited classical axiom (behind the non-load-bearing Remark 5.2).** Extensional equality of functions
`ℕ → ℕ` is undecidable: there is no decision procedure `decide` with `decide f g = true ↔ ∀ n, f n = g n`.
This is the Rice-flavored fact the paper cites (Rice 1953; Budd–Angluin 1982) for Remark 5.2's connection to
equivalent-mutant detection. It is recorded as an axiom in the standard idiom for a cited undecidability.

IMPORTANT: this axiom is **not** the proof of Thm C. Relative-completeness undecidability (§5) is the direct
`L_g` reduction from finitely-generated submonoid membership (Mihailova 1958 / Lohrey–Steinberg 2008), a paper
proof intentionally not formalized here. -/
axiom func_equality_undecidable :
    ¬∃ (decide : (ℕ → ℕ) → (ℕ → ℕ) → Bool),
      ∀ f g, decide f g = true ↔ (∀ n, f n = g n)
