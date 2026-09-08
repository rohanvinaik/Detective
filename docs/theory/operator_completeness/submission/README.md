# Theory artifacts — audit reconciliation, 2026-09-07

The current audit-corrected working text is ../KNOWABILITY.md. Generate its IEEE-format
artifact with `python build_knowability.py`, then `tectonic knowability_ieee.tex` from this
folder. Tectonic is installed locally. This is a working artifact, not a submitted paper.

paper_lncs.tex and paper_lncs.pdf retain the earlier adequacy-completeness paper. These
historical companion artifacts are not generated from KNOWABILITY.md. Venue and deadline
notes in earlier drafts have not been reverified here.

The seven previously missing theorems are restored in ../proofs/adequacy_completeness.lean.
That development now has 29 checked theorems, including three audit counterexamples.
See ../proofs/README.md for the exact formal scope and pinned Lean/Mathlib environment.
NEGATIVE_SPECIFICATION.md already contains a superseding note distinguishing
adequacy-completeness from the archived monoid-generation analysis.

The new computability and probabilistic arguments in the prose are not claimed as Lean results.
