# The Completeness of Mutation Operators

A self-contained paper on **when a finite set of mutation operators is complete** — i.e. whether it can express
every behavioral distinction a faulty implementation could exhibit at the output. Modelling an output-operator
family as a finite generating set of the codomain transformation monoid, the answer is a **trichotomy**:

- **finite codomain** — absolute completeness (generate the whole monoid) is *decidable in polynomial time* and
  *constructive* (a complete basis of size 3, from `rank(T_n) = 3`);
- **infinite codomain** — absolute completeness by a finite family is *impossible*, by a one-line cardinality
  argument (a countable closure cannot equal an uncountable monoid), so only *relative* completeness (against a
  finitely-presented target of admissible deviations) is meaningful there;
- **relative completeness** — *undecidable* in general (reduction from the word problem for finitely-presented
  semigroups), but with the boundary drawn by the **presentation**, not the carrier: restricted
  (confluent/terminating) presentations are decidable.

Underneath all three sits a hard **ceiling**: output operators act by post-composition, so they can never
express a fault that separates two inputs the correct function identifies — output-mutation completeness is
completeness for *output recodings*, a strict subspace of behavioral faults.

The result stands on standard foundations — mutation testing (coupling hypothesis, sufficient operators,
subsumption), transformation-semigroup theory (rank of `T_n`), computability (the word problem; Rice's
theorem), and learning theory (teaching dimension / sample compression) — and does not depend on any particular
tool or research program.

## Contents

| File | What |
|---|---|
| `OPERATOR_COMPLETENESS.md` | the paper (Thm A finite decidable-in-P + rank-3 basis; Thm B infinite impossibility; Thm C relative undecidability; Thm D the trichotomy; Prop 2.3 the post-composition ceiling; Conj E dimension-bound foreclosure — *conjectural*; Prop F ASDL coverage — a decidable invariant, not a completeness criterion) |
| `LITERATURE_PI_COMPLETENESS.md` | the 42-source verified bibliography, by area, with URLs |
| `proofs/T2_generated.lean` | machine-checked: two maps generate the full transformation monoid `T₂` |
| `proofs/T3_generated_rank3.lean` | machine-checked: a 3-cycle + transposition + rank-2 idempotent generate all 27 maps of `T₃` (the rank-3 basis) |
| `proofs/operator_completeness.lean` | **statements only** — the finite-decidability signature (proof is the P-time algorithm of §3, not a Lean term) and one cited classical axiom (function-equality undecidability, the ingredient behind Thm C.2). *Not* the word-problem reduction. |

## The machine-checked fragment (Theorem A base cases)

`T2_generated` and `T3_generated_rank3` are **fully proven in Lean 4 / Mathlib** (no `sorry`), each discharging
the finite enumeration by `decide`. Their axiom footprint is **clean**:

```
'T2_generated'        depends on axioms: [propext, Classical.choice, Quot.sound]
'T3_generated_rank3'  depends on axioms: [propext, Classical.choice, Quot.sound]
```

— the standard Lean/Mathlib base, no `sorryAx`. To reproduce, drop the `.lean` files into a Lean 4 project with
Mathlib (`lake exe cache get`), then `#print axioms T2_generated` / `#print axioms T3_generated_rank3`.

**What is and isn't machine-checked.** The finite *generation* base cases (n=2,3) are machine-checked. The
finite *decidability in P* (Thm A.2) is a paper proof (rank argument + Schreier–Sims); the umbrella file's
decidability `instance` is a signature stub, not a Lean proof. Thm B (infinite impossibility) is an elementary
cardinality argument. Thm C (relative undecidability) is a paper proof citing Post/Markov and Rice; the umbrella
axiom records the Rice-flavored function-equality fact behind Thm C.2, **not** the word-problem reduction of
Thm C.1. Conjecture E is explicitly conjectural — the basis-to-compression bridge it needs (beyond Doliwa's
maximum-class equivalence) is not established here.

*Status: draft; the finite generation base cases are machine-checked and axiom-audited clean, the finite
decidability and Thm C are rigorous paper proofs, Thm B is elementary, and E is an open conjecture. Not
peer-reviewed.*
