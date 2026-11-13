# implement-knowability-ii

Turn the Knowability II thesis — what a survivor of the wider mutation regime can say — into working
behaviour in Wesker and Detective: a theorem-derived operator basis per site, a typed survivor state
decided by an exact solver over the function's premises, three resolvers (structure, corpus, teacher), a
premise ledger, κ-ordered teacher questions with surprise, and a five-number report in place of one kill
rate. The planning home for both repositories is here, as `complete-paired-repair` is for the repair plan.

**Theory:** [`docs/theory/knowability_ii/KNOWABILITY_II.md`](../../../docs/theory/knowability_ii/KNOWABILITY_II.md).
**Handoff block (carry verbatim):** [`docs/theory/knowability_ii/CONSTRAINT_BLOCK.md`](../../../docs/theory/knowability_ii/CONSTRAINT_BLOCK.md).
**Wesker's side of the plan:** `Wesker/docs/KNOWABILITY_II_WESKER.md` (a pointer back here plus the engine
stages, so a Wesker-only session has what it needs).

## How to resume this change cold

1. Read `CONSTRAINT_BLOCK.md` (five minutes). It has the constraints, the forbidden actions and the one
   next action.
2. Prove the local pair resolves (AGENTS.md "Standing invocation"):
   ```bash
   export PP=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker
   PYTHONPATH=$PP .venv/bin/python -c "import Detective, Wesker; print(Detective.__file__); print(Wesker.__file__)"
   ```
3. Run `python docs/theory/knowability_ii/local_guards_check.py` — it must print `OK`.
4. Open [`tasks.md`](tasks.md). Every unchecked box is remaining work. Take the first unchecked task whose
   dependencies are checked. Each task names its files, its functions, its pure decision (house style:
   named string codes, `(pure — pinned)`), its intent test, and its acceptance line.
5. Gate before every commit (AGENTS.md): the full suite under `PYTHONPATH=$PP .venv/bin/python -m pytest`,
   then `uvx ruff@0.16.7 format Detective tests`, `uvx ruff@0.16.7 check Detective tests`,
   `uvx ruff@0.16.7 format --check .` (whole tree). Wesker: the same with `Wesker tests`.
6. Commit as a checkpoint per task; push per wave, after asking.

## Relation to the repair plan

`complete-paired-repair` says new capabilities are Type (2) additions that need their own proposal. This is
that proposal. It does not mark any repair accepted, and it does not depend on the unaccepted B-items
except where a task says so (W2 needs the site trace to run under the in-process path; it does not need
the isolated path's containment items). Where a task touches a seam the repair plan also touches, the
task names the repair item and defers to it.

## What this change is not

- Not a rewrite. Every stage is additive and defaults off; with site tracing and propagation off, every
  existing verdict, certificate, golden and `--json` field is byte-identical (V5 is the gate).
- Not a new dependency. The solver is standard-library exact enumeration.
- Not a promotion of anything. `UNPROVEN`, `proposed`, `UNDETERMINED` stay what they are.
