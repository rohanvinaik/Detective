import Mathlib

/-!
# Operator Completeness — statements and one cited axiom (NOT the machine-checked proofs)

This umbrella file is **statements only**. The machine-checked content of the paper lives in the two
sibling files, each fully proven (no `sorry`) and `#print axioms`-clean:

- `T2_generated.lean`        — Thm A.1 (n = 2): swap + constant generate `T₂` on `Fin 2`.
- `T3_generated_rank3.lean`  — Thm A.1 (n = 3): 3-cycle + transposition + rank-2 idempotent generate `T₃`.

What this file adds is (a) the *signature* of the finite-decidability result, whose actual proof is the
polynomial-time algorithm in the paper (§3, Thm A.2) and is not formalized as a Lean term; and (b) **one
cited classical fact, recorded as an axiom** — the Rice-flavored ingredient behind Thm C.2.

Honest scope, so nothing here is oversold:
- Thm A.1 (finite generation, n = 2,3): **proven** — in the two sibling files, not here.
- Thm A.2 (finite decidability, in P): the `instance` below is a **signature stub**; the proof is the
  rank-argument + Schreier–Sims of paper §3, not a Lean term. It carries `sorry` deliberately.
- Thm B (infinite impossibility): **elementary cardinality** (paper §4); a countable closure cannot equal
  the uncountable `Function.End R`. Not formalized here (one line on paper).
- Thm C.1 (relative undecidability): a **paper proof** (§5) reducing from the Post/Markov word problem. It is
  **NOT** the axiom below and is not formalized here.
- The axiom `func_equality_undecidable` below is the classical undecidability of extensional equality of
  `ℕ → ℕ` functions — the ingredient behind Thm C.2 (Rice 1953 / Budd–Angluin 1982). It is an adjacent
  cited fact, **not** a formalization of Π-completeness undecidability.
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

/-- **Cited classical axiom (behind Thm C.2).** Extensional equality of functions `ℕ → ℕ` is undecidable:
there is no decision procedure `decide` with `decide f g = true ↔ ∀ n, f n = g n`. This is the
Rice-flavored ingredient the paper cites (Rice 1953; Budd–Angluin 1982) for the equivalence reduction
(§5, Thm C.2). It is recorded as an axiom in the standard idiom for a cited undecidability.

IMPORTANT: this axiom is **not** a formalization of Thm C.1 (the word-problem reduction for *relative*
Π-completeness). That reduction is a paper proof (§5) + Lemma C.1a; it is intentionally not formalized here. -/
axiom func_equality_undecidable :
    ¬∃ (decide : (ℕ → ℕ) → (ℕ → ℕ) → Bool),
      ∀ f g, decide f g = true ↔ (∀ n, f n = g n)
