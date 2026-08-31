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
for you.

---

## Green is not proof

A passing test proves your code returned the right answer once. `assert add(1, 1) == 2` passes —
and so does `3*a - b`, and so does `a*b + 1`, and so do infinitely many functions that are not
addition. Every example you add leaves infinitely many impostors standing through the points.
And the suite was never a contract in the first place; nobody wrote it to be one. It accumulated —
a regression here, a bug report there, the happy path from the afternoon the function was born.
It is a residue, and you are about to stake a rewrite on it.

The gap does not close with more examples. It closes by killing the freedoms that matter. Swap
the `+` in `add` for a `-`, and every non-trivial input separates addition from its impostors at
once; forbid the degenerate `0 + 0 = 0`, and nothing trivial can hide. Two moves, and addition is
pinned — for every input, provably, rather than "probably, after forty cases." Detective derives
those moves from two things that are already free: the operators your code actually runs, and the
tests you already wrote. Then it writes them.

> **A suite that kills every killable mutant of a function is that function's behavioral
> contract.** A rewrite that keeps it green preserved the behavior the contract pins.

The suite is not the product. It is the receipt.

---

## The second strand

The design is three billion years old. Life probes what a structure actually commits to by
mutating it, and filters the variants through selection — and then it does the part that matters:
it proofreads. DNA is carried in two strands so that errors can be *corrected*, not merely
detected. The repair enzymes do not know what a gene is for, and they do not need to; the second
copy of the information is enough to restore the first. One channel of evidence detects. Two
channels correct.

This tool is the second strand for code.

---

## The three agents

The work is divided among three programs.

**[Wesker](https://github.com/rohanvinaik/Wesker) is the mutating force.** Given one function, it
derives every small variant that function's own operators admit — a `+` bent to a `-`, a boundary
nudged, a branch forced — and runs each against the tests you have. It is a violent instrument on
purpose: breaking a thing every way it can break is how you learn which of its properties were
*held* and which merely *happened*. A mutant your suite kills is a commitment your tests enforce.
A mutant that walks away is a degree of freedom — behavior nothing on earth is checking — and the
comfortable, hand-built, intuition-tested function turns out to be mostly degrees of freedom.
What survives Wesker unbroken was never really specified. Its selection guarantees are
machine-checked in Lean; the violence is exact.

**Detective reads the trail and writes the story.** It speaks for the branches — the
investigator, not the commander: it does not choose its missions, and it does not decide what
your code is for. Handed the wreckage — which mutants died, which walked — it reconstructs what
the function truly commits to, writes the *minimal* suite that pins every pinnable behavior, and
proves any restructuring preserved what was pinned. Where the trail runs out, it files the report
most software never writes. A survivor nothing distinguishes is recorded `candidate-equivalent —
UNPROVEN`, never promoted to fact. A value whose meaning lives in your head and not in the code
is asked for, never invented. A function that reads the clock is declined — no test written there
would stay true. Every verdict states which of four things it is: measured and clean; measured
and wrong; not measurable this run; not measurable by anyone. The reports go to someone higher
up. That someone is you.

**[Uroboros](https://github.com/rohanvinaik/Uroboros) closes the loop.** Point it at a codebase
and it runs the method with nobody watching: one function driven to a pinned suite or an honest
hand-back, then the next, then the next — until there is nothing left to prove. There is no seat
for an intelligence to climb into: a small local model is woken at exactly one step, to select an
input value into a typed schema, and does nothing else. What can be pinned is pinned. What can be
split at a proven seam is split. What needs a human — a domain value, a fixture, an intent —
comes back as a short list a person clears over coffee, each item a *different kind* of decision,
never blurred. The name is the oldest symbol there is: the loop grinds its own output through
itself, and the tools are run on the tools — Detective's functions are pinned by Detective, and
the first work order its planner ever produced pointed at a function inside Wesker.

Its final form — the loop that trains the very thing it measures, the ruler becoming the reward —
is designed, unbuilt, and marked as such in the theory. The serpent is patient.

---

## See it, write it, prove it

**`diagnose`** reads a function and names what your tests leave unpinned, then names the one
thing to run next. It writes nothing.

**`converge`** writes the smallest suite that pins the function, and stops where your inputs run
out — naming what it could not reach, with the input that would:

```
$ detective converge stats.py::anomaly_score

  0% → 73% (27/37 behaviors pinned) · 4 tests written

  4 behaviors nothing distinguishes — each with the input that would:
    return round(score, 4)   →  round(score, 2)   supply a score with a nonzero 3rd–4th decimal
    if deviation > peak:      →  >=   supply an input where deviation == peak
```

**`decompose --apply`** rewrites the function and keeps the change only if that suite proves the
behavior held. `--apply` is a gate, not a hope: a red baseline can never produce a proof, and
nothing reaches your source that the re-run did not clear. When it cannot prove, it refuses, and
prints exactly what it needs.

**`receipt` / `verify-rewrite`** bracket an *arbitrary* rewrite — including one a model wrote, in
whatever style it pleased: snapshot the proof suite before, replay the obligations after, and
answer `PRESERVED` / `CHANGED` / `UNREVIEWED` with the distinguishing input named. A model's
confidence is not evidence; a receipt is.

Pointed at [`boltons`](https://github.com/mahmoud/boltons) — a utility library it had never
seen — it wrote a mutation-complete suite for `slugify`, which had no tests of its own, and then
**rejected** its own proposed split of `backoff_iter`: the suite it had just written proved the
change unsafe, on a function nobody on the project had ever read. Source untouched.

What lands on disk is ordinary pytest — no runtime dependency, every test carrying the warrant it
was written under. And the claims about the *method* are machine-checked where it matters: what a
full mutation score certifies is now a theorem rather than folklore, proved in Lean down to the
kernel, with the undecidable residue held out honestly instead of absorbed. The formal
development lives in [`docs/theory/`](./docs/theory/).

---

## The second question: is it well made?

Pinning behavior settles what code *does*. Whether the code is any good — fast, cohesive,
right-sized, doing one thing — has belonged, for the whole history of the field, to taste: the
practiced eye of expensive people, applied by hand, encoded nowhere. *Structure and
Interpretation of Computer Programs* wrote the aesthetic down forty years ago; holding to it has
been a discipline of memory ever since.

Detective's second half runs the aesthetic as a control system, over the same measurements the
proofs use.

- **Measurement, not opinion.** Each function is read on independent axes — complexity, cohesion,
  behavioral density (a signal no linter has: how many distinct behaviors the mutation engine
  finds per line), the priced cost of splitting it — every reading taken against norms **mined
  from the codebase itself** and validated out-of-sample, never imported from a style guide. Axes
  vote and interfere; they are never averaged, because a weighted sum of incommensurable things
  is how every scoring tool before this one lied.
- **Recognition, not judgment.** The expert's "this is a lookup done the slow way" is a *shape* —
  and shapes are recognizable, mechanically, conservatively, each with a specific transform and a
  proof obligation attached.
- **A plan, not a score.** The output is a budgeted work order, and everything declined carries
  its reason, named. Pointed at its own codebase: 66 functions flagged, 5 funded now, 7 waiting
  on budget, 54 recorded as "no recipe exists yet." A plan that cannot explain its refusals is
  just a score with ambition.
- **The person, seated exactly.** What no measurement reaches — what the code is *for*, and the
  cases where the evidence genuinely disagrees with itself — routes to a human by name, because
  the theory proves no machine can settle it. Taste is not eliminated. It is located.

---

## Why now

For the whole history of the field you could have code that was cheap or code that was right.
Machines now write code faster than anyone can review it, and each generated function arrives
with two things attached: an unknown specification status, and a fluent justification for it. A
green suite settles nothing when the model wrote the tests too.

Run that same slop through this loop and it changes category — because the quality was never
going to live in the generator. It lives in the process. A cheap local model producing slop by
the yard is a perfectly good input to a gate that is exact, and what survives the gate is not the
model's code anymore: it is code carrying a contract no fluency could have weakened, doing
exactly what you intended, verified to the theoretical ceiling of what any process can know about
a program — a ceiling this project proved, and then built to. Every other craft industrialized
the day quality moved out of the artisan's hands and into the process, and that day always waited
on one instrument: the gauge. This is the gauge. The one thing the process cannot absorb, by
theorem, is what any of it is *for* — the interpretation in *Structure and Interpretation* — and
that stays with you, now with a receipt for everything else.

And it is a ratchet. Once a function is mutation-complete it cannot silently regress — the
contract is a file on disk that stays green or goes red. Codebases normally accumulate entropy.
This accumulates irreversible specification, one function at a time.

---

## Where it stops

One function at a time, deterministic, narrow on purpose.

- **It preserves behavior, not correctness.** If the original was wrong, the rewrite is wrong the
  same way — provably. The person who knows the difference is the one holding the map.
- **It pins to the extent the code is pure.** Clock, filesystem, environment — declined, not
  guessed, with the remedy named.
- **It will not invent a domain value.** Meaning that lives in your head, you supply once; it
  asks, rather than fabricating a confident number over a guess.
- **A search is not a proof of equivalence.** Undistinguishable survivors stay `UNPROVEN`; `flag`
  records a human judgment that a later distinguishing input overrides.
- **One function, not a repo — for proof.** There is no repo-scale mutation profile, and never
  will be. The traversal of a whole codebase belongs to Uroboros, which does it one proven
  function at a time.

Detective was pointed at the engine it runs on. It found one of that engine's own functions
unspecifiable — the return value was a set of memory addresses, different every run, so no
assertion could ever hold — and declined to write the test. It was right, and the function was
changed.

A tool that will say that about its author's code will say anything.

---

## Run it

```bash
uv add detective-spec          # or: uv pip install detective-spec
detective diagnose path/to/your_file.py::your_function   # start here — writes nothing
```

It installs as `detective-spec`, imports as `Detective`, and runs as `detective`. Every command
closes by naming the one thing to run next.

| Command | Writes | Answers |
|---|---|---|
| `diagnose file.py::fn` | nothing | what does this do, and what do I run next? |
| `converge file.py::fn` | test files | give me a complete, minimal suite |
| `decompose file.py::fn --apply` | your source | split it — applied only when proven behavior-preserving |
| `audit file.py::fn [--check]` | nothing | is my suite complete? minimal? (CI-gateable) |
| `receipt` / `verify-rewrite` | ledger | bracket an arbitrary rewrite with proof |
| `parsimony path/` | nothing | where does this codebase drift from the discipline? (advisory) |
| `flag file.py::fn ID [--fence]` | ledger | record equivalence — or author a must-not |
| `regime` | config | how does this repo import and test — and can the suite reach my file? |

Exit codes are an epistemic logic, not pass/fail: `0` clean · `1` a measured gap or refusal ·
`2` your world is wrong — fix that, not the code · `3` a measurement it could not trust — re-run.
The determined-false / cannot-determine boundary the whole tool is built on, machine-readable.
Full reference, module map, and the symptom→cause debug map: [ARCHITECTURE.md](./ARCHITECTURE.md).
For agents, the MCP surface: `uv pip install 'detective-spec[mcp]'` — five tools over the same
library, every reply ending in `DO THIS:`, `STOP.`, or `DONE:`.

---

*Mutation to reveal what was never held. Investigation to write down what was. A loop that runs
the method on everything, including itself, until what remains is the smallest true version of
what you meant. The engine is [Wesker](https://github.com/rohanvinaik/Wesker); the endgame is
[Uroboros](https://github.com/rohanvinaik/Uroboros); the story in the middle is Detective.*

*MIT — Rohan Vinaik.*
