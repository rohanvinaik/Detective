# Detective

**Refactor a Python function — or let a model rewrite it — and prove the behavior didn't change.**

<p align="center">
  <a href="https://github.com/rohanvinaik/Detective/actions/workflows/ci.yml"><img src="https://github.com/rohanvinaik/Detective/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/detective-spec/"><img src="https://img.shields.io/pypi/v/detective-spec.svg?color=3367d6" alt="PyPI"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-3367d6.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-3367d6.svg" alt="Python 3.11+"></a>
</p>

`Deterministic · No LLM · Applies nothing it cannot prove`

Your suite is green. Detective loosened a comparison in your code — `deviation > threshold`
became `deviation >= threshold` — and the suite is still green:

```diff
- if deviation > threshold:
+ if deviation >= threshold:      # every test you wrote still passes
```

That is a real change to what your function computes, and nothing you wrote noticed. Every
refactor you have ever shipped placed its bet in that gap. So does every line a model writes
for you. By the end of this page you will know how to close it — for one function, provably —
and exactly what the proof does and does not promise.

---

## Green is not proof

A passing test proves your code returned the right answer once. It does not prove it returns
*only* right answers, and no number of examples closes the difference. The smallest function
there is shows why: `assert add(1, 1) == 2` passes — and so does `3*a - b`, and so does
`a*b + 1`, and so do infinitely many functions that are not addition. Every example you add
leaves infinitely many curves still standing through the points.

And the suite was never a contract in the first place. Nobody wrote it to be one. It
accumulated — a regression here, a bug report there, the happy path from the afternoon the
function was born. It is a residue, and you are about to stake a rewrite on it.

You do not close that gap with more examples. You close it by killing the degrees of freedom
that matter. Swap the `+` in `add` for a `-`, and every non-trivial input separates addition
from its impostors at once. Forbid the degenerate `0 + 0 = 0`, and nothing trivial can hide.
Two moves, and addition is pinned — for every input, provably, rather than "probably, after
forty cases."

Detective does that for your function. It reads the operators your code actually runs, takes
the tests you already wrote, and works out the moves that pin the behavior those two things
imply. Then it writes them.

> **A suite that kills every killable mutant of a function is that function's behavioral
> contract.** A rewrite that keeps it green preserved the behavior the contract pins.

The suite is not the product. It is the receipt.

---

## How it works: three programs, one method

The idea is borrowed from the oldest debugging system there is. Biology probes what an organism
actually commits to by mutating it and seeing what survives — and it keeps its information on
two strands, so an error can be *corrected* against the second copy, not merely noticed. This
project is that architecture, applied to code, split across three tools:

**[Wesker](https://github.com/rohanvinaik/Wesker) mutates.** Given one function, it derives
every small way the code's own operators can be perturbed — a `+` bent to `-`, a boundary
nudged, a branch forced — and runs each variant against your tests. A mutant your suite kills
is a commitment your tests enforce. A mutant that survives is a degree of freedom: behavior
nothing is checking. Most hand-built functions turn out to be mostly degrees of freedom, which
is the uncomfortable fact the whole method rests on. Wesker's guarantees are machine-checked
in Lean; the mutants are derived, not sampled.

**Detective investigates.** This tool — the one this page is about. Handed Wesker's results,
it reconstructs what the function truly commits to, writes the *minimal* suite that pins every
pinnable behavior, and proves any restructuring preserved what was pinned. Where the evidence
runs out, it says so instead of guessing: a survivor nothing can distinguish is recorded
`candidate-equivalent — UNPROVEN`, never promoted to fact; a value whose meaning lives in your
head is asked for, never invented; a function that reads the clock is declined, because any
golden test of it would be green now and red a second later. Detective does not decide what
your code is for. It writes down what your code does, completely, and hands the intent
questions to the one party who can answer them.

**[Uroboros](https://github.com/rohanvinaik/Uroboros) runs the loop.** Point it at a codebase
and it applies the method with nobody watching: one function driven to a pinned suite or an
honest hand-back, then the next, until there is nothing left to prove. What needs a human — a
domain value, a fixture, a judgment — comes back as a short list, each item a different kind
of decision. The name is the serpent eating its own tail, and it is meant literally: the tools
are run on the tools. Detective's own functions are pinned by Detective, and the first work
order its planner ever produced pointed at a function inside Wesker.

Once, pointed at the engine it runs on, Detective found one of that engine's functions
unspecifiable — the return value was a set of memory addresses, different every run, so no
assertion could ever hold. It declined to write the test. It was right, and the function was
changed. A tool that will say that about its author's code will say anything.

---

## See it, write it, prove it

**`diagnose`** reads a function and tells you what your tests leave unpinned, then names the
one thing to run next. It writes nothing.

**`converge`** writes the smallest suite that pins the function, and stops where your inputs
run out — naming what it could not reach, with the input that would:

```
$ detective converge stats.py::anomaly_score

  0% → 73% (27/37 behaviors pinned) · 4 tests written

  4 behaviors nothing distinguishes — each with the input that would:
    return round(score, 4)   →  round(score, 2)   supply a score with a nonzero 3rd–4th decimal
    if deviation > peak:      →  >=   supply an input where deviation == peak
```

**`decompose --apply`** rewrites the function and keeps the change only if the suite proves
the behavior held. A red baseline can never produce a proof, and nothing reaches your source
that the re-run did not clear. Three outcomes, never blurred: `APPLIED` (proven), `rejected`
(a test caught it — your file untouched), `unproven` (no complete suite yet — nothing tried).

**`receipt` / `verify-rewrite`** bracket an *arbitrary* rewrite — including one a model wrote:
snapshot the proof suite before, replay the obligations after, and answer `PRESERVED` /
`CHANGED` / `UNREVIEWED`, with the distinguishing input named when the answer is `CHANGED`.
This is the artifact the AI-coding era was missing. A green suite means nothing when the model
wrote the tests too; that is self-certification. A receipt is evidence no fluency can fake,
produced deterministically, on a CPU, the same bytes every run.

What lands on disk is ordinary pytest — no runtime dependency on Detective, every test
carrying the warrant it was written under, every test already in the minimal cover.

---

## The second question: is it well made?

Pinning behavior settles what code *does*. Whether the code is any *good* — fast, cohesive,
right-sized — has always belonged to taste: the practiced eye of experienced engineers,
applied by hand, encoded nowhere. Detective's second half treats that eye as something you can
build, and the design is three refusals:

- **No imported thresholds.** Each function is measured on independent axes — complexity,
  cohesion, behavioral density (a signal only the mutation engine can see: how many distinct
  behaviors per line), the priced cost of splitting — against norms mined from the codebase
  itself and validated out-of-sample. The axes vote and interfere; they are never averaged,
  because a weighted sum of incommensurable things is how scoring tools lie.
- **No judgment where recognition suffices.** The expert's "this is a lookup done the slow
  way" is a *shape*. Shapes are recognizable — mechanically, conservatively, each with a
  specific fix and a proof obligation attached. Recognition proposes; the proof gate decides.
- **No scores.** The output is a plan: *these functions, these transforms, this estimated
  cost, proofs available* — and for everything declined, the reason, named. Pointed at its own
  codebase, the advisory layer flagged 66 functions; the plan resolved them into 5 do-now,
  7 when-there's-budget, and 54 honest "no safe recipe exists yet."

What no measurement reaches — what the code is *for*, and the cases where the evidence
genuinely disagrees with itself — routes to a human, by name. That boundary is a theorem in
this project, not a disclaimer: the formal development in [`docs/theory/`](./docs/theory/)
characterizes exactly what a mutation score can certify (machine-checked in Lean, down to the
kernel) and exactly where mechanical knowledge ends and authorship begins. Taste is not
eliminated. It is located, and everything around it stops pretending to be taste.

---

## What this is not

The fence matters as much as the field. Detective is **not a linter** — it runs your code
against derived variants; it holds no style opinions it can't prove or measure. It is **not
coverage** — a covered line whose mutants survive proves nothing, and Detective counts a
mutant killed only when an *assertion* distinguishes the output, reporting mere crashes
separately rather than spending them on its own score. It is **not an LLM tool** — no model
anywhere in the loop; the same input produces the same bytes. And it is **not a correctness
prover** — it preserves behavior, not intent. If the original was wrong, the rewrite is wrong
the same way, provably; the person who knows the difference is the one it hands the map to.

The rest of the boundary, stated because the precise claim is the strong one:

- **It pins to the extent the code is pure.** Clock, filesystem, environment: declined, not
  guessed, with the remedy named.
- **A search is not a proof of equivalence.** Undistinguishable survivors stay `UNPROVEN`;
  `flag` records a human judgment that a later distinguishing input overrides.
- **One function at a time — for proof.** There is no repo-scale mutation profile, and never
  will be. The one repo-scale surface (`parsimony`) is advisory and says so; the whole-repo
  traversal belongs to Uroboros, which does it one proven function at a time.

---

## Run it

```bash
uv add detective-spec          # or: uv pip install detective-spec
detective diagnose path/to/your_file.py::your_function   # start here — writes nothing
```

It installs as `detective-spec`, imports as `Detective`, runs as `detective`. Every command
closes by naming the one thing to run next.

| Command | Writes | Answers |
|---|---|---|
| `diagnose file.py::fn` | nothing | what does this do, and what do I run next? |
| `converge file.py::fn` | test files | give me a complete, minimal suite |
| `decompose file.py::fn --apply` | your source | split it — applied only when proven behavior-preserving |
| `audit file.py::fn [--check]` | nothing | is my suite complete? minimal? (CI-gateable) |
| `receipt` / `verify-rewrite` | ledger | bracket an arbitrary rewrite with proof |
| `parsimony path/` | nothing | where does this codebase drift from the discipline? (advisory) |
| `flag file.py::fn ID [--fence]` | ledger | record a survivor equivalent — or author a must-not |
| `regime` | config | how does this repo import and test — and can the suite reach my file? |

Exit codes are an epistemic logic, not pass/fail: `0` clean · `1` a measured gap or refusal ·
`2` a precondition — your world is wrong, fix that · `3` a measurement it could not trust —
re-run. Full reference, module map, and the symptom→cause debug map:
[ARCHITECTURE.md](./ARCHITECTURE.md). For agents, the MCP surface:
`uv pip install 'detective-spec[mcp]'` — the same library, every reply ending in `DO THIS:`,
`STOP.`, or `DONE:`.

---

## What you get

Three things, to say them again plainly. A **contract**: your function's behavior, pinned by a
minimal suite that fails on any change — a ratchet, because once complete it cannot silently
regress; codebases normally accumulate entropy, and this accumulates specification. A
**receipt**: proof that a rewrite — yours or a machine's — changed nothing, which is the piece
of paper the age of generated code was missing. And a **boundary**: a proven line between what
a tool can know about your code and what only you can say, with the tool doing everything on
its side and handing you, by name, the questions that were always yours.

---

*Mutation to reveal what was never held. Investigation to write down what was. A loop that
runs the method on everything — including itself — until what remains is the smallest true
version of what you meant. The engine is [Wesker](https://github.com/rohanvinaik/Wesker); the
loop is [Uroboros](https://github.com/rohanvinaik/Uroboros); the story in the middle is
Detective. MIT — Rohan Vinaik.*
