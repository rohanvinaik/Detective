# Archive — the monoid-generation notion (superseded)

This directory holds the earlier paper on operator completeness under the **transformation-monoid generation**
notion (`Π` complete `:⟺ ⟨Π⟩ = T(R)`), and its Lean proofs. It is retained for the record and **superseded** by
the active paper one directory up, `../ADEQUACY_COMPLETENESS.md`.

**Why superseded.** Generation is not the notion mutation testing requires: killing a family's generators does
not entail killing their composites (composition can erase the moved values that caused the generators to be
killed), so "`⟨Π⟩ = T(R)`" says nothing about what a passing mutation score certifies. The successor replaces
generation with **adequacy-completeness** — an operator family is measured by what killing its mutants
certifies, uniformly over programs and suites — which yields a footprint characterization, a value-guard basis,
the exact "score = output coverage" ceiling, and coupling as a corollary.

**What here is still correct.** The finite algebra (`rank(T_n) = 3`, the `T2`/`T3` generation witnesses) and the
infinite-codomain cardinality impossibility (`pi_incomplete_infinite`) are correct as stated; they are simply
about a notion that does not characterize test adequacy. The paper's decidability *dichotomy/trichotomy* framing
and its relative-completeness = submonoid-membership analysis are also correct as computability facts.

## Contents

| File | What |
|---|---|
| `OPERATOR_COMPLETENESS.md` | the superseded generation-notion paper |
| `proofs/T2_generated.lean` | machine-checked: two maps generate `T₂` |
| `proofs/T3_generated_rank3.lean` | machine-checked: the rank-3 basis generates all 27 maps of `T₃` |
| `proofs/pi_incomplete_infinite.lean` | machine-checked: infinite `R` ⇒ a f.g. submonoid ≠ `⊤` |
| `proofs/operator_completeness.lean` | documentation index (no declarations; earlier inconsistent axiom removed) |

The three closed proofs are `#print axioms`-clean (`[propext, Classical.choice, Quot.sound]`, no `sorryAx`).
