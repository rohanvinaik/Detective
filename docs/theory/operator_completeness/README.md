# The Completeness of Mutation Operators

A self-contained paper on **when a finite set of mutation operators is complete** — i.e. whether it can
express every behavioral distinction a faulty implementation could exhibit. The answer is a **decidability
dichotomy**: modelling an output-operator family as a finite generating set of the codomain transformation
monoid, completeness is *decidable and constructive* on a finite codomain and *undecidable* on a
structured/infinite one, with a *foreclosure* result ruling out any capacity-dimension-bounded minimal
complete basis.

The result stands on standard foundations — mutation testing (coupling hypothesis, sufficient operators,
subsumption), transformation-semigroup theory (rank of `T_n`), computability (the word problem; Rice's
theorem), and learning theory (teaching dimension / sample compression) — and does not depend on any
particular tool or research program.

## Contents

| File | What |
|---|---|
| `OPERATOR_COMPLETENESS.md` | the paper (Thm A finite/constructive, B undecidable, C dichotomy, D compression foreclosure, E ASDL syntactic criterion; Lemmas B.1a, D.a) |
| `LITERATURE_PI_COMPLETENESS.md` | the 42-source verified bibliography, by area, with URLs |
| `proofs/operator_completeness.lean` | the Lean source: the finite generation witnesses + the undecidability axiom |
| `proofs/T2_generated.lean` | machine-checked: two maps generate the full transformation monoid `T₂` |
| `proofs/T3_generated_rank3.lean` | machine-checked: a 3-cycle + transposition + rank-2 idempotent generate all 27 maps of `T₃` (the rank-3 basis) |

## The machine-checked fragment (Theorem A base cases)

`T2_generated` and `T3_generated_rank3` are **fully proven in Lean 4 / Mathlib** (no `sorry`), each
discharging the finite enumeration by `decide`. Their axiom footprint is **clean**:

```
'T2_generated'        depends on axioms: [propext, Classical.choice, Quot.sound]
'T3_generated_rank3'  depends on axioms: [propext, Classical.choice, Quot.sound]
```

— the standard Lean/Mathlib base, no `sorryAx`. To reproduce, drop the `.lean` files into a Lean 4 project
with Mathlib (`lake exe cache get`), then `#print axioms T2_generated` / `#print axioms T3_generated_rank3`.

Theorems B–E are rigorous **paper proofs** citing already-proven classical results (Post/Markov word problem,
Rice's theorem, the Pabbaraju and Hanneke–Moran–Waknine compression impossibilities); those dependencies are
not in Mathlib and are not re-formalized. The undecidability is recorded in `operator_completeness.lean` as an
axiom citing the classical result.

*Status: draft; the finite fragment is machine-checked and axiom-audited clean, B–E are rigorous paper proofs.
Not peer-reviewed.*
