# Detective

**Refactor a Python function — or let a model rewrite it — and prove the behavior didn't change.**

<p align="center">
  <a href="https://github.com/rohanvinaik/Detective/actions/workflows/ci.yml"><img src="https://github.com/rohanvinaik/Detective/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/detective-spec/"><img src="https://img.shields.io/pypi/v/detective-spec.svg?color=3367d6" alt="PyPI"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-3367d6.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-3367d6.svg" alt="Python 3.11+"></a>
</p>

`Deterministic · No LLM · Applies nothing it cannot prove`

Your suite is green. Detective just loosened a comparison in your code — a `>` into a `>=` —
and your suite is still green:

```diff
- if deviation > threshold:
+ if deviation >= threshold:      # every test passes
```

That was a real change to what your function computes, and nothing you wrote noticed. This
page follows one question wherever it leads — the tool, the theory, and the two strange
companions it keeps all fall out of asking it honestly:

**What do your tests actually know about your code?**

---

## What a green suite knows

Less than it feels like. A passing test knows your code gave the right answer *once*. It does
not know your code gives only right answers, and no number of examples closes the gap: through
any finite set of points run infinitely many functions that are not yours. `assert add(1, 1)
== 2` is passed by addition — and by `3*a - b`, and by an unbounded crowd of impostors that
will go on passing while you refactor, while a model rewrites, while years of edits land on
top.

And in fairness to your suite, it was never designed to know things. It accumulated: a
regression here, a bug report there, the happy path from the afternoon the function was born.
Nobody wrote it as a contract; it is a residue. Every change you have ever shipped placed its
bet on that residue. So does every line a model writes for you.

There is a way to find out what a suite actually knows. It is not gentle.

---

## The question, asked seriously

**[Wesker](https://github.com/rohanvinaik/Wesker) asks it.** Given one function, it derives
every small way that function's own operators could have been otherwise — each `+` bent to a
`-`, each boundary nudged, each branch forced — and turns the whole pack loose on your tests.
The method is violent on purpose: you learn which of a thing's properties are *held*, rather
than merely present, by trying to take each one away. A mutant your suite kills is something
your tests genuinely know. A mutant that strolls out unharmed is a freedom — a way your
function could change tonight with no alarm going off — and a comfortable, hand-built,
code-reviewed function turns out, on honest measurement, to be mostly freedoms. The engine
wastes no motion while it does this: one mutant per behavioral question, under a selection
bound machine-checked in Lean. When it hurts you, it hurts you efficiently.

What the violence leaves behind is a trail — *this died, this walked* — and a trail is not an
answer. Someone has to read it.

---

## Reading the trail

**Detective is the reader.** Handed the wreckage, it reconstructs what your function actually
commits to, and writes the smallest suite that pins every behavior that can be pinned — so
nothing can change what the function computes without a test going red:

```
$ detective converge stats.py::anomaly_score

  0% → 73% (27/37 behaviors pinned) · 4 tests written

  4 behaviors nothing distinguishes — each with the input that would:
    return round(score, 4)   →  round(score, 2)   supply a score with a nonzero 3rd–4th decimal
    if deviation > peak:      →  >=   supply an input where deviation == peak
```

Read the residual again, because the manner is the substance: where the trail runs out,
Detective stops. A survivor no input distinguishes is recorded `candidate-equivalent —
UNPROVEN`, and no amount of failing to kill it will ever promote it to "equivalent." A
parameter whose meaning lives in your head is asked for — once — never invented. A function
that reads the clock is declined outright: a test pinned to the current time is green today
and a lie by Tuesday, and Detective would rather refuse than know something falsely. Every
verdict names its own kind — measured and clean, measured and wrong, not measurable this run,
not measurable by anyone — because those are four different facts, and a tool that blurs them
has opinions, not knowledge.

What lands on disk is ordinary pytest, with no runtime dependency. But it is a different kind
of object from the suite you had this morning. **A suite that kills every killable mutant is
that function's behavioral contract** — and from here on it does contract work. Rewrite the
function however you like: split it, fuse it, hand it to a model with no supervision and
questionable taste. `decompose --apply` touches your source only when the contract proves the
behavior held; `receipt` and `verify-rewrite` bracket a rewrite from anywhere and answer
`PRESERVED`, `CHANGED` — distinguishing input named — or `UNREVIEWED`. No one vouches for
anything. The suite is not the product; it is the receipt.

The first time this gate met a stranger's code — [`boltons`](https://github.com/mahmoud/boltons),
a utility library, zero configuration — it wrote a complete suite for `slugify`, which had no
tests of its own, then proposed a split of `backoff_iter`, checked its own proposal against
the contract it had just written, found the behavior would change, and rejected itself. File
untouched.

---

## The second question

Knowing what a function *does* says nothing about whether it is any *good* — small enough,
cohesive, doing one thing, worth splitting. For the whole history of the field that question
has belonged to taste: the practiced eye of expensive people, encoded nowhere. Detective's
second half puts it on the same measurement basis as the proofs. Each function is read on
independent axes — complexity, cohesion, behavioral density per line (a signal only a mutation
engine has), the priced cost of a split — against norms mined from your own codebase and
validated out-of-sample, never imported from a style guide.

The axes vote, and they are never averaged into a score, because a weighted sum of
incommensurables is how every code-quality number before this one lied. The output is a plan
whose every refusal is named: pointed at its own repository, it flagged 66 functions, funded
5, deferred 7 on budget, and recorded 54 as "no safe recipe exists yet." And what no
measurement reaches — what the code is *for*, and the cases where the evidence honestly
disagrees with itself — is routed, explicitly, to a person. Taste is not eliminated. It is
located.

---

## The ceiling

Add up the ledger. What your function does: knowable, mechanically, operator by operator.
Whether a rewrite preserved it: knowable. Whether it is well made: measurable, priceable,
plannable. This is the point where a page like this is supposed to reassure you that there
will still be something left for humans, and the reassurance is usually a vibe. Here it is a
theorem. The same mathematics that pushes mechanical knowledge to its maximum also proves the
maximum exists — machine-checked, down to the kernel: **what a program is *for* is not in the
program.** Not latently, not statistically, not at any scale of analysis — it was never
written down. Text carries effects; meaning stays with authors. Every tool on this page is
built against that line: total automation below it, a full stop at it, and every stopped
question — the flagged survivor, the asked-for input, the ambiguous verdict — filed upward to
the one seat the mathematics reserves. The seat is you. Nothing that runs on a CPU can fill
it, and that is a proof, not a promise.

Which quietly settles the question of the age. If verification is mechanical and exact, the
generator stops mattering: a cheap local model producing slop by the yard is a perfectly
acceptable input to a gate that cannot be argued with, because what leaves the gate is no
longer the model's code — it is code that provably does what you meant, which was the only
thing anyone ever wanted from code. For seventy years you could have programs that were cheap,
or programs that were right, and the entire discipline lived inside that tradeoff. It just
ended.

---

## The loop, closed

**[Uroboros](https://github.com/rohanvinaik/Uroboros) is that ending, taken all the way.** A
process that provably cannot cross into meaning is a process you can leave alone with
everything — so point it at a codebase and walk away. It takes one function to completion —
pinned, or honestly handed back — then the next, then the next, until there is nothing left to
prove. A small local model is woken at exactly one step, to choose an input value into a typed
schema; it writes no code and steers nothing, and there is no seat for it to climb into,
because the only seat in this system is yours. Whatever needs you comes back as a short list,
each item typed by the kind of decision it is — a domain value, a fixture, a judgment — never
blurred. And the loop eats its own tail on purpose: Detective's functions are pinned by
Detective, and the first work order its planner ever produced named a function inside Wesker.

---

## Where it stops

A system this hungry owes you the list of what it will not eat.

- **It preserves behavior, not correctness.** If the original was wrong, the rewrite is
  provably wrong in the same way. Telling the difference requires knowing what the code is
  for — see above, the seat.
- **Pure code pins fully; impure code is declined, with the remedy named** — a clock to
  freeze, a fixture to supply — never guessed at.
- **It invents no domain values.** A meaning the code doesn't hold, you supply once.
- **A failed search proves nothing.** An undistinguished survivor stays `UNPROVEN`; your
  `flag` is a recorded judgment, and a later distinguishing input outranks it.
- **One function at a time, always.** There is no repo-scale mutation profile and there never
  will be; whole codebases are Uroboros's job, one proven function after another.

And once, pointed at the engine it runs on, Detective found a function whose return value was
a set of memory addresses — different every run, impossible to assert on — and declined to
write the test, stating why. It was right. The function was changed.

---

## Run it

```bash
uv add detective-spec          # or: uv pip install detective-spec
detective diagnose path/to/file.py::function     # start here — writes nothing
```

Installs as `detective-spec`, imports as `Detective`, runs as `detective`. Every command ends
by naming the next one.

| Command | Writes | Answers |
|---|---|---|
| `diagnose file.py::fn` | nothing | what does this do, and what do I run next? |
| `converge file.py::fn` | test files | the complete, minimal suite |
| `decompose file.py::fn --apply` | your source | split it — only under proof |
| `audit file.py::fn [--check]` | nothing | is my suite complete? minimal? (CI-gateable) |
| `receipt` / `verify-rewrite` | ledger | bracket an arbitrary rewrite with proof |
| `parsimony path/` | nothing | where does this codebase drift? (advisory) |
| `flag file.py::fn ID [--fence]` | ledger | record an equivalence — or author a must-not |
| `regime` | config | can a verdict here even be trusted? |

Exit codes are epistemics, not pass/fail: `0` clean · `1` a measured gap, or a refusal · `2`
your world is wrong — fix that, not the code · `3` the measurement can't be trusted — re-run.
Machine consumers get the same verdicts as JSON; agents get an MCP surface
(`detective-spec[mcp]`) whose every reply ends in `DO THIS:`, `STOP.`, or `DONE:`. The full
command reference and the symptom→cause map live in [ARCHITECTURE.md](./ARCHITECTURE.md); the
theorems — the ceiling, the two-sign teaching set, the effect/meaning boundary — live in
[`docs/theory/`](./docs/theory/), in full academic dress.

---

*Wesker asks the question by breaking things. Detective answers what can be answered, and
files the rest upward. Uroboros asks it of everything, forever, itself included. What cannot
be taken from you, this system proves. Everything else, it handles.*

*MIT — Rohan Vinaik.*
