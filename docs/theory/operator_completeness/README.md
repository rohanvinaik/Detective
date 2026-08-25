# The Completeness of Mutation Operators

A self-contained paper on **when a finite set of mutation operators is complete** — i.e. whether it can express
every behavioral distinction a faulty implementation could exhibit at the output. Modelling an output-operator
family as a finite generating set of the codomain transformation monoid — equivalently, as a submonoid-
membership problem — the answer is a clean **2×2 landscape** (notion × carrier):

| | **absolute** (generate all of `T(R)`) | **relative** (generate a named target `S_R`) |
|---|---|---|
| **finite `R`** | **P** — rank argument, size-3 basis (`rank(T_n)=3`) | **PSPACE-complete** — monoid membership (Kozen 1977) |
| **infinite `R`** | **impossible** for finite Π — one-line cardinality | **undecidable in general** — *is* f.g. submonoid membership |

The two right-hand cells are the corrections to the naive "decidable iff finite" picture. Relative completeness
*is* the finitely-generated **submonoid-membership** problem, and its frontier is **membership, not the word
problem**: there are monoids with decidable word problem but undecidable submonoid membership (Mihailova 1958;
Lohrey–Steinberg 2008), so a "nice" (confluent/terminating) presentation does not by itself make completeness
decidable.

Underneath every cell sits a hard **ceiling**: output operators act by post-composition, so they can never
express a fault that separates two inputs the correct function identifies — output-mutation completeness is
completeness for *output recodings*, a strict subspace of behavioral faults.

The result stands on standard foundations — mutation testing (coupling hypothesis, sufficient operators,
subsumption), transformation-semigroup theory (rank of `T_n`, Kozen membership), computability (submonoid
membership; Rice's theorem), and learning theory (teaching dimension / sample compression) — and does not depend
on any particular
tool or research program.

## Contents

| File | What |
|---|---|
| `OPERATOR_COMPLETENESS.md` | the paper (Thm A finite: absolute in P + relative PSPACE-complete + rank-3 basis; Thm B infinite-absolute impossibility; Thm C relative ≡ submonoid membership, undecidable; Thm D the 2×2 landscape; Prop 2.3 the post-composition ceiling; Conj E dimension-bound foreclosure — *conjectural*; Prop F ASDL coverage — a decidable invariant, not a completeness criterion) |
| `LITERATURE_PI_COMPLETENESS.md` | the 42-source verified bibliography, by area, with URLs |
| `proofs/T2_generated.lean` | machine-checked (Thm A): two maps generate the full transformation monoid `T₂` |
| `proofs/T3_generated_rank3.lean` | machine-checked (Thm A): a 3-cycle + transposition + rank-2 idempotent generate all 27 maps of `T₃` (the rank-3 basis) |
| `proofs/pi_incomplete_infinite.lean` | machine-checked (Thm B): on an infinite codomain, a finitely generated submonoid of `Function.End R` cannot be everything (countable closure vs uncountable monoid) |
| `proofs/operator_completeness.lean` | **documentation index only** — no declarations (no `axiom`, no `sorry`); points to the three closed proofs and notes which results are paper-only (A.2, A.3, Thm C). An earlier inconsistent function-equality `axiom` was removed (see the file's provenance note). |

## The machine-checked fragment (both machine-checked corners of the landscape)

`T2_generated`, `T3_generated_rank3` (Thm A base cases) **and** `pi_incomplete_infinite` (Thm B) are **fully
proven in Lean 4 / Mathlib** (no `sorry`) — the generation witnesses by `decide` over the finite monoid, the
impossibility by a countable-closure-vs-uncountable-monoid cardinality argument. Their axiom footprints are
**clean**:

```
'T2_generated'            depends on axioms: [propext, Classical.choice, Quot.sound]
'T3_generated_rank3'      depends on axioms: [propext, Classical.choice, Quot.sound]
'pi_incomplete_infinite'  depends on axioms: [propext, Classical.choice, Quot.sound]
```

— the standard Lean/Mathlib base, no `sorryAx`. To reproduce, drop the `.lean` files into a Lean 4 project with
Mathlib (`lake exe cache get`), then `#print axioms <name>`.

**What is and isn't machine-checked.** *Both left-column corners of the landscape* are machine-checked: the finite
*generation* base cases (Thm A, n=2,3) and the infinite *impossibility* (Thm B). The finite *decidability in P*
(Thm A.2) and *relative* PSPACE-completeness (Thm A.3) are paper proofs (rank argument + Schreier–Sims; Kozen
membership). Thm C (relative undecidability) is a paper proof by the direct `L_g` reduction — relative
completeness *is* finitely-generated submonoid membership, undecidable by Mihailova 1958 / Lohrey–Steinberg 2008
(results not in Mathlib). The umbrella file introduces **no declarations** (no axiom, no `sorry`); an earlier
inconsistent function-equality axiom was removed. Conjecture E is explicitly conjectural — the basis-to-compression
bridge it needs (beyond Doliwa's maximum-class equivalence) is not established here.

*Status: draft; both machine-checked corners of the landscape (Thm A basis, Thm B impossibility) are machine-checked and
axiom-audited clean, the finite decidability and Thm C are rigorous paper proofs, and E is an open conjecture.
Not peer-reviewed.*
