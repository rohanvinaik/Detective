# Detective

**Refactor a Python function — or let a model rewrite it — and prove the behavior didn't change.**

<p align="center">
  <a href="https://github.com/rohanvinaik/Detective/actions/workflows/ci.yml"><img src="https://github.com/rohanvinaik/Detective/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/detective-spec/"><img src="https://img.shields.io/pypi/v/detective-spec.svg?color=3367d6" alt="PyPI"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-3367d6.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-3367d6.svg" alt="Python 3.11+"></a>
</p>

`Deterministic · No LLM · Applies nothing it cannot prove`

---

## The gamble

Nearly all software rests on a quiet bet. We check that programs work by testing them — running
examples, confirming answers. But an example is not a guarantee. `assert add(1, 1) == 2` passes —
and so does `3*a - b`, and so does `a*b + 1`, and so do infinitely many functions that are not
addition. Every test you add leaves infinitely many impostors standing through the points. The
suite was never a contract; nobody wrote it to be one. It accumulated — a regression here, a bug
report there, the happy path from the afternoon the function was born. It is a residue, and every
change you have ever shipped — every refactor, every cleanup, every line a model wrote for you —
placed its bet in the gap between what the tests check and what the code does.

Entropy wins that bet by default. Codebases rot the way all unmaintained order rots: each edit a
small mutation, each green run a little false comfort, until the functions nobody dares touch are
exactly the ones that most need touching. The industry's answer has been judgment — seniority,
review, taste — which is to say: the answer has been to hope the right person is looking.

This project's wager is that the gap can be closed instead of straddled. Not with more examples,
and not with a bigger model vouching harder, but by drawing — with machine-checked mathematics —
the exact line between **what a machine can know about a program and what only its author can
say**, and then automating everything on the machine's side of that line. Both questions that
matter live there: *does it do what it's supposed to?* and *is it well made?*

The design is older than software. Life runs on exactly this architecture: mutation as the probe
that reveals what an organism's structure actually commits to, selection as the filter, and — the
part biology understood three billion years before we did — **proofreading**. DNA is carried in
two strands so that errors can be *corrected*, not merely detected; the repair enzymes don't know
what a gene is *for*, and they don't need to — the second copy of the information is enough to
restore the first. One channel of evidence detects. Two channels correct. This tool is the second
strand for code.

---

## The three agents

The work is divided among three programs, and the division is the thesis.

**[Wesker](https://github.com/rohanvinaik/Wesker) is the mutating force.** It does not read
intentions and it does not extend courtesy. Given one function, it derives every small way that
function's actual operators can be perturbed — a `+` bent to a `-`, a boundary nudged, a branch
forced — and runs each variant against the tests you have. It is a violent instrument on purpose:
the point of breaking a thing every way it can be broken is to learn which of its properties were
*held* and which merely *happened*. A mutant your suite kills is a commitment your tests enforce.
A mutant that survives is a degree of freedom — behavior nothing on earth is checking — and the
comfortable, hand-built, intuition-tested function turns out to be mostly degrees of freedom. What
survives Wesker unbroken was never really specified. The engine's own guarantees are machine-
checked in Lean; the violence is exact.

**Detective reads the trail and writes the story.** It is the investigator, not the commander: it
does not choose its missions, and it does not decide what your code is for. Handed Wesker's wreckage
— which mutants died, which walked away — it reconstructs what the function truly commits to, writes
the *minimal* test suite that pins every pinnable behavior, and proves any restructuring preserved
what was pinned. Where the trail runs out, it does something almost no software does: it files an
honest incident report and hands it up. A survivor nothing can distinguish is recorded
`candidate-equivalent — UNPROVEN`, never promoted to fact. A value whose meaning lives in your head
and not in the code is *asked for*, never invented. A function that reads the clock is declined —
"no test I could write here would stay true" — rather than pinned to a lie. Every verdict states
which of four things it is: measured and clean; measured and wrong; not measurable this run; not
measurable by anyone. The reports are for someone higher up. That someone is you.

**[Uroboros](https://github.com/rohanvinaik/Uroboros) closes the loop.** Point it at a codebase
and it runs the method with nobody watching: one function driven to a pinned suite or an honest
residual, then the next, then the next — Wesker's force, Detective's judgment, no strong
intelligence anywhere in the loop and no seat for one to climb into — until there is nothing left
to prove. What can be pinned is pinned. What can be split at a proven seam is split. What needs a
human — a domain value, a fixture, an intent — comes back as a short list a person clears over
coffee, each item a *different kind* of decision, never blurred. The name is the oldest symbol
there is: the serpent consuming its own tail. The loop grinds its own output through itself; the
tools are run on the tools — Detective's functions are pinned by Detective, and the first work
order its planner ever produced pointed at a function inside Wesker. A system that will say *that*
about its own foundations will say anything. This is the endgame the other two exist for: not a
report about code, but a codebase transformed — every function reduced toward the most minimal,
most fully-specified version of what it was already trying to be, and a receipt for each step.

---

## See it, write it, prove it

**`diagnose`** reads a function and tells you what your tests leave unpinned, then names the one
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
nothing reaches your source that the re-run did not clear.

**`receipt` / `verify-rewrite`** bracket an *arbitrary* rewrite — including one a model wrote, in
whatever style it pleased, even in another language: snapshot the proof suite before, replay the
obligations after, and answer `PRESERVED` / `CHANGED` / `UNREVIEWED` with the distinguishing input
named. A model's confidence is not evidence; a receipt is. What lands on disk is ordinary pytest —
no runtime dependency, every test carrying the warrant it was written under:

> **A suite that kills every killable mutant of a function is that function's behavioral
> contract.** A rewrite that keeps it green preserved the behavior the contract pins.

And the guarantees are about the *method*, machine-checked where it matters: what a full mutation
score certifies is now a theorem, not a folklore — it certifies exactly what it certifies, the
boundary is proved in Lean down to the kernel, and the undecidable residue is held out honestly
rather than absorbed. The formal development lives in [`docs/theory/`](./docs/theory/).

---

## The second question: is it well made?

Pinning behavior settles what code *does*. It says nothing about whether the code is any good —
fast, cohesive, right-sized, doing one thing — and for the whole history of the field that question
has belonged to taste: the practiced eye of expensive people, applied by hand, encoded nowhere.
*Structure and Interpretation of Computer Programs* wrote the aesthetic down forty years ago;
holding to it has been a discipline of memory ever since.

Detective's second half makes the aesthetic *decidable* — not by flattening it into a score, but by
running it as a control system over the same measurement basis the proofs use:

- **Measurement, not opinion.** Each function is read on independent axes — complexity, cohesion,
  behavioral density (a signal no linter has: how many distinct behaviors the mutation engine finds
  per line), the priced cost of splitting it — every reading taken against norms **mined from the
  codebase itself** and validated out-of-sample, never imported from a style guide. Axes vote and
  interfere; they are never averaged, because a weighted sum of incommensurable things is how every
  scoring tool before this one lied.
- **Recognition, not judgment.** The expert's "this is a lookup done the slow way" is a *shape* —
  and shapes are recognizable, mechanically, conservatively, with a specific fix and a proof
  obligation attached to each. Where the expert's eye was a career, the template is a library entry.
- **A plan, not a score.** The output is a budgeted work order: *these functions, these transforms,
  this estimated cost, proofs available* — and for everything declined, the reason, named: fenced,
  escalated, no safe recipe yet, over budget. Pointed at its own codebase, the advisory layer flagged
  66 functions; the controller resolved them into 5 do-now, 7 when-there's-budget, and 54 honest
  "no recipe exists yet." A plan that cannot explain its residual is just a score with ambition.
- **The person, seated exactly.** What no measurement reaches — what the code is *for*, and the
  cases where the evidence genuinely disagrees with itself — routes to a human by name, because the
  theory proves no machine can settle it. Taste is not eliminated. It is *located*, and everything
  around it stops pretending to be taste.

---

## Where it stops — the human's seat

One function at a time, deterministic, narrow on purpose. Every line here is load-bearing.

- **It preserves behavior, not correctness.** If the original was wrong, the rewrite is wrong the
  same way — provably. Specification completeness is not correctness, and the person who knows the
  difference is the one it hands the map to.
- **It pins to the extent the code is pure.** Clock, filesystem, environment — declined, not
  guessed, with the remedy named.
- **It will not invent a domain value.** Meaning that lives in your head, you supply once; it asks
  rather than fabricating a confident number over a guess.
- **A search is not a proof of equivalence.** Undistinguishable survivors stay `UNPROVEN`; `flag`
  records a human judgment that a later distinguishing input overrides.
- **One function, not a repo — for proof.** There is no repo-scale mutation profile, and never will
  be; the one repo-scale surface is advisory and says so. The traversal of a whole codebase belongs
  to Uroboros, which does it one proven function at a time.

These are not disclaimers. They are the point. A tool that claimed more would know less — and the
entire value of the receipt is that it is exactly as large as the truth.

---

## Why now

Machines now write code faster than people can review it, which means the scarce resource stopped
being generation and became *trust*. A green suite means nothing when the model wrote the tests
too; that is self-certification, and confidence has never been evidence. What this project makes
is the artifact that gap was waiting for: a contract no fluency can fake, a receipt a skeptic
cannot argue with, produced on a CPU, the same bytes every run.

And it is a ratchet. Once a function is mutation-complete it cannot silently regress — the
contract is a file on disk that stays green or goes red. Codebases normally accumulate entropy.
This accumulates irreversible specification, one function at a time, and hands the only questions
that ever needed a person to the person. The suite is not the product. It is the receipt.

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
`2` your world is wrong, fix that · `3` a measurement it could not trust — re-run. The
determined-false / cannot-determine boundary the whole tool is built on, machine-readable.
Full reference, module map, and the symptom→cause debug map: [ARCHITECTURE.md](./ARCHITECTURE.md).
For agents, the MCP surface: `uv pip install 'detective-spec[mcp]'` — five tools over the same
library, every reply ending in `DO THIS:`, `STOP.`, or `DONE:`.

---

*Mutation to reveal what was never held. Investigation to write down what was. A loop that runs
the method on everything, including itself, until what remains is the smallest true version of
what you meant. The engine is [Wesker](https://github.com/rohanvinaik/Wesker); the endgame is
[Uroboros](https://github.com/rohanvinaik/Uroboros); the story in the middle is Detective.*

*MIT — Rohan Vinaik.*
