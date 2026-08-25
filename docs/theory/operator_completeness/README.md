# What a Mutation Score Certifies — adequacy-completeness for output mutation

The active paper in this directory is **`ADEQUACY_COMPLETENESS.md`**. It gives a completeness notion for
mutation operators that is neither program- nor test-suite-relative, by measuring an operator family by **what
killing its mutants certifies** rather than by the mutants it can produce.

Restricted to **output mutation** (operators that perturb the returned value), the key observation is that for
adequacy an operator *is* its **footprint** `Mov(p) = {r : p(r) ≠ r}`: equivalence and killing depend only on
which values an operator moves, not where it sends them. The results:

- **Characterization (Thm 3.2).** `Π` is adequacy-complete for `Γ` iff every target footprint is the union of
  the `Π`-footprints contained in it.
- **Value-guard basis (Cor 4.1, 4.1a).** On `n` values the minimal absolutely-complete family has size exactly
  `n` (the singleton "value guards"); on an infinite codomain **no finite operator family is absolutely
  complete**. Descartes-style constants are complete iff `n = 2` (Cor 4.2).
- **Ceiling (Thm 4.4).** An absolute score of 1 certifies **exactly output coverage** — every reachable output
  observed — and nothing more.
- **Coupling as a corollary (Thm 6.1),** for higher-order *output* mutants.
- **Program-independence (Prop 7.2)** via the detection factoring `Det(p∘f) = f⁻¹(Mov(p))`; **decidability
  spectrum (Thm 5.2)** through footprint containment; **minimum certifying suite = `|f(D)|` (Thm 8.1).**

The main theorem and every consequence — and the bridge down to real programs `f : D → R` and finite suites —
are **machine-checked in Lean 4 / Mathlib** (`proofs/adequacy_completeness.lean`), each theorem `#print
axioms`-clean (`[propext, Classical.choice, Quot.sound]`, no `sorryAx`). Reproduce with `lake exe cache get`
then `#print axioms progComplete_characterization`.

The result stands on standard foundations — mutation testing (coupling, sufficient operators, subsumption),
computability, and the classical teaching-dimension notion — and does not depend on any particular tool.

## Contents

| Path | What |
|---|---|
| `ADEQUACY_COMPLETENESS.md` | **the active paper** (adequacy-completeness for output mutation) |
| `proofs/adequacy_completeness.lean` | its full machine-checked development (characterization + consequences + program↔footprint bridge) |
| `LITERATURE_PI_COMPLETENESS.md` | the source-verified bibliography (shared) |
| `archive/` | the **superseded** monoid-*generation* notion (paper + its 4 closed proofs); see `archive/README.md` |

## Why an archive?

An earlier line of work (now in `archive/`) modelled completeness as *generation of the transformation monoid*.
That notion is not what mutation testing requires: killing a family's generators need not kill their composites,
so "generates `T(R)`" does not characterize what a passing score certifies. `ADEQUACY_COMPLETENESS.md` replaces
generation with adequacy. The archived finite algebra and cardinality impossibility remain correct; they are
simply about a notion that does not track test adequacy.
