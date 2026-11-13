# Knowability II — what a survivor of the wider regime can say

The paper in `../operator_completeness/` (KNOWABILITY.md; IEEE form in `submission/`) characterizes
exactly what a passing score against **output mutation** knows: output coverage, nothing more, with the
value guards as the minimal sufficient regime. Wesker and Detective run a wider regime than that, and
for a survivor of the wider regime the tools can today say only `killable`, `candidate-equivalent —
UNPROVEN`, or a fixture/structural caveat.

**`KNOWABILITY_II.md`** is the follow-up. It says what the wider regime *can* know, in three steps:

1. the paper's Theorem 3.2 is exact **at every mutation site** once the site's local value is the codomain
   (weak mutation) — run on a comparison's truth table it reproduces the Kaminski sufficient ROR set, and
   run on Wesker's live BOUNDARY table it finds a completeness gap (`<`/`>` lack the `!=` guard);
2. a survivor's residual is a **typed state** (reach / infect / propagate as constraints decided by an exact
   solver over the function's premises), with a finite alphabet of states whose remedies differ;
3. open states are resolved by **three resolvers** — structure, the corpus, the teacher — and the teacher's
   queue is **ordered before it is resolved** by κ (how much an answer collapses) and surprise (how
   improbable a survival is), both emitted as brackets.

| Path | What |
|---|---|
| `KNOWABILITY_II.md` | the document: definitions, Thm 3.1 / Cor 3.2 / Cor 3.3 / Prop 3.4, the alphabet (§5), three resolvers (§6), κ and surprise (§7), the two-signed category map (§8), the surface rules (§9), predictions (§11), status ledger (§12) |
| `CONSTRAINT_BLOCK.md` | the handoff block — carry verbatim into any summary; constraints with reasons, resolved questions, the one next action |
| `local_guards_check.py` | Cor 3.2 and Cor 3.3, exhaustive, no dependencies; exit 0 iff both hold |

**Build plan:** `openspec/changes/implement-knowability-ii/` (proposal, design, `tasks.md` with every stage for
both repositories, literal enough to execute cold).

**Reading order for a cold start:** `CONSTRAINT_BLOCK.md` → `KNOWABILITY_II.md` §1, §5, §6 → the tasks.

**What this document does not change.** The paper's results and Lean development; NEGATIVE_SPECIFICATION's
theorems; the one-function law (ARCHITECTURE §11); the value-vs-run precedence (ARCHITECTURE §0); the rule
that `UNPROVEN` is never promoted by assertion. Where this document and those disagree on present behaviour,
ARCHITECTURE wins; where it disagrees with a formal document on theory, the formal document wins and the
disagreement is a bug to file here.
