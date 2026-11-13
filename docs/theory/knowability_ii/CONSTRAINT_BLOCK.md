# Knowability II — Constraint Block · carry VERBATIM into any summary or handoff

<!-- Constraints WITH reasons; resolved questions stated AS RESOLVED; the next action as ONE imperative;
the sources that can contradict this block named LAST — and they win. Section references are to
docs/theory/knowability_ii/KNOWABILITY_II.md unless prefixed (NS = NEGATIVE_SPECIFICATION.md,
CD = COMMUNICATING_DETERMINISM.md, SW = SIGNIFICANCE_WEIGHTING.md, KP = the knowability paper). -->

**Remove-X check this block must pass:** remove the conversation that produced it. Can a fresh agent
recover the constraints, the build order, the forbidden actions, and pick the same next action? If not,
the block is broken, not the reader.

---

## Constraints (each with the why that gives it mass)

1. **A survivor is a state, not a verdict** *(§5; CD §3 — two states whose remedies differ never share a
   sign)*. The codes are `killer_ready · dead_site · reachable_if · local_equivalent · masked ·
   pseudo_tested_oracle · open_at_bound · inconsistent_premises` beside today's `value_residual ·
   fixture_residual · structural_residual · genuine_equivalent`. `dof_zero` is never printed: it becomes a
   test.

2. **The literal level routes to code, never to a flag** *(§5 rule 1)*. `dead_site`, `masked`, and a
   `local_equivalent` by invariant are the code contradicting itself. Today they print as
   `candidate-equivalent — UNPROVEN` and invite a flag; that is the collision the build splits first.

3. **The solver proposes; execution decides** *(§5 rule 2; the standing rule that nothing is promoted by
   assertion)*. A satisfying assignment is a candidate `--input`, run through `classify_survivor`; only an
   observed difference writes a test. No solver verdict ever mints a kill or a COMPLETE.

4. **Three resolvers, in order: structure, corpus, teacher** *(§6; NS Thm 6.2, Def 4.2, §9)*. DOF⁰
   collapses mechanically. A corpus candidate is a `proposed` premise until spine-sourced and
   plurality-preserving (NS Def 9.3, machine-checked); a proposed premise never changes a verdict.

5. **Premises are ledger entries with an origin and an S-version** *(§6 Def 6.2; NS §18 Q8)*. `flag`,
   `--fence`, `censor` and `default` all write here; `--input` is a witness and does not. Every κ and
   every five-number report carries the S-version it was computed against.

6. **κ is relative three ways and the graph is induced, never drawn** *(§7 Def 7.1, Prop 7.2; SW §13)*.
   κ(v | S) = survivors whose solver verdict changes on adopting v, recomputed per S by re-entailment. The
   call graph is the quotient (Prop 7.3); d lives there and is UNMEASURED on code.

7. **Brackets, never points; measured bases, never defaults** *(§7 Def 7.4; SW §2)*. κ prints
   [floor, ceiling]; surprise uses the function's own propagation rate q and prints `unmeasured` when no
   killed pair exists. A missing base is a missing measurement, not zero.

8. **The one-function law holds** *(ARCHITECTURE §11)*. Premises arrive as entries; no run widens to the
   suite or the repository. Caller facts come in as censors with origins, never as a wider trace.

9. **Nothing changes with site tracing and propagation off** *(§10; build item V5)*. Every existing
   certificate, golden and `--json` field is byte-identical modulo new optional fields that default to
   absent. `SCORED_DISPOSITIONS` is unchanged; the site trace is annotation, not disposition.

10. **Zero dependencies** *(Wesker's promise; NS Def 4.4)*. The solver is standard-library exact
    enumeration with `Fraction`, modelled on TrialLedger `layer2/entail.py`, not a solver dependency.

11. **The local theorem is weak mutation** *(§3 Thm 3.1, Remark 3.5)*. It governs which mutants to
    generate at a site (the DOF count per site is a theorem), not whether a kill at the site is a kill at
    the return. Reach and propagate stay per-program constraints.

## Resolved questions (stated as resolved)

- *Is the κ graph the call graph or the premise-obligation graph?* **Both, at two resolutions**: the
  premise→survivor graph (fine, induced by the solver) for computing κ; the call graph (its quotient by
  function) for bridges and d. NS §18 Q1's choice of the call graph stands for d.
- *Does the paper address program-text operators?* **Its theorem does, at the site** (Thm 3.1); its
  no-universal-certificate result (KP Prop 7.2) is untouched.
- *Where do state and exceptions enter the paper?* **Through the codomain** (KP §9 with ω = projection
  onto R for a return-only assertion; R ∪ {raise E} for exceptions; §8 table).
- *Is Wesker's BOUNDARY table complete?* **No** (Cor 3.3, checked): `<`/`>` lack the `!=` guard; `==`/`!=`
  on orderable operands lack the one-sided guards. Repair is W1.
- *What is the human's job?* **The finite triage, ordered** (NS Def 12.1; §7 Def 7.6): answer the max-κ
  premise, stop at κ → 0.

## Forbidden actions

- Promoting `UNPROVEN`, `proposed` or `UNDETERMINED` to anything stronger by assertion.
- Printing a κ without its bracket and S-version; printing a surprise with a defaulted q.
- Letting a corpus candidate, an advisory lens, or a solver verdict gate a certificate.
- Inviting a `flag` on a `dead_site` or `masked` survivor.
- Adding a dependency to Wesker or Detective for the solver.
- Changing `SCORED_DISPOSITIONS`, the value-vs-run precedence, or any verdict when the new features are off.
- Filtering Detective's or Wesker's output, or printing their exit status in its place (AGENTS.md).

## The next action (one imperative)

**Run `python docs/theory/knowability_ii/local_guards_check.py`, then open
`openspec/changes/implement-knowability-ii/tasks.md` and execute Stage 0, then W1.**

## Sources that can contradict this block — and win

`docs/theory/knowability_ii/KNOWABILITY_II.md` (theory) · `docs/theory/NEGATIVE_SPECIFICATION.md` and
`docs/theory/operator_completeness/KNOWABILITY.md` (formal priors) · `ARCHITECTURE.md` (present
behaviour) · `AGENTS.md` (the working discipline) · the live code of Wesker and Detective.
