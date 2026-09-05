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

That was a real change to what your function computes, and nothing you wrote noticed. The
rest of this page follows one question wherever it goes — the tool, the theory, and the two
strange companions it keeps are all just what happens when you ask it seriously:

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
than merely present, by trying to take each one away. That is an old idea in learning and a
forgotten one in testing. In 1970 Patrick Winston taught a program what an arch was by showing
it arches — and by showing it *near-misses*, non-arches that differed in one crucial respect,
which did most of the teaching. Software testing kept the examples and dropped the
near-misses; a test has no slot for a non-example. A mutant is a near-miss, and Wesker makes
them by the thousand. One your suite kills is something your tests genuinely know. One that
strolls out unharmed is a freedom — a way your function could change tonight with no alarm
going off — and a comfortable, hand-built, code-reviewed function turns out, measured, to be
mostly freedoms. The engine wastes no motion doing this: one mutant per behavioral question,
never forty phrasings of the same one, with the selection guarantee proved in Lean. When it
hurts you, it hurts you efficiently. It is named for a captain who marched his own squad into
a house full of monsters to learn which ones they could kill, and it has the same loyalties.

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

Look at the bottom half of that output. Where the trail runs out, Detective stops. A survivor no input distinguishes is recorded `candidate-equivalent —
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
engine has), the priced cost of a split — against norms mined from your own codebase, checked
against the half of it they weren't mined from, and never imported from a style guide.

The axes vote, and they are never averaged into a score, because a weighted sum of
incommensurables is how code-quality scores lie. The output is a plan
whose every refusal is named: pointed at its own repository, it flagged 66 functions, funded
5, deferred 7 on budget, and recorded 54 as "no safe recipe exists yet." And what no
measurement reaches — what the code is *for*, and the cases where the evidence honestly
disagrees with itself — is routed, explicitly, to a person. Taste is not eliminated. It is
located.

---

## The ceiling

Add up the ledger. What your function does: knowable, mechanically, operator by operator.
Whether a rewrite preserved it: knowable. Whether it is well made: measurable, priceable,
plannable. This is usually the point where a page reassures you that there will still be
something left for humans, and usually the reassurance is a vibe. Here it is a theorem,
machine-checked in Lean: **what a program is *for* is not in the program.** When you wrote
`price >= floor`, the file recorded your decision that an ordering matters — but *why* it
matters, what the function is for, what would count as wrong even if every test passed: none
of that ever made it into the text, and no analysis at any scale recovers what was never put
there. So every tool on this page runs by one rule. Below that line, automate everything; at
it, stop and ask. The flagged survivor, the requested input, the ambiguous verdict — each is
the same event: the machine reaching the edge of what the file contains, and handing the
question to whoever holds the rest. Usually that's you. The theorem is indifferent to what you
are made of — a person, a model a person has briefed, anything that can hold an intention and
be wrong about it. It insists on one thing only: that the party who says what the code is for
is never the party that proves the code does it. Fuse the two and you have a machine grading
its own homework. Keep them apart and the intent can come from anywhere, and the proof stays a
proof. That is not a courtesy. It is the theorem's conclusion.

This has a cheerful consequence for the era of generated code. If verification is mechanical
and exact, the generator stops mattering: a cheap local model producing slop by the yard is a
perfectly acceptable input to a gate that cannot be argued with, because what leaves the gate
is no longer the model's code — it is code that provably does what you meant. For seventy
years, programs could be cheap or they could be right. That tradeoff had a good run.

---

## The loop, closed

**[Uroboros](https://github.com/rohanvinaik/Uroboros) takes that consequence all the way.** A
process that provably cannot cross into meaning is a process you can leave alone with
everything — so point it at a codebase and walk away. It takes one function to completion —
pinned, or honestly handed back — then the next, then the next, until there is nothing left to
prove. A small local model is woken at exactly one step, to choose an input value into a typed
schema; it writes no code and steers nothing, and there is no seat for it to climb into: the
proving seat cannot be shared, and the intent seat is already held by whoever wrote the tests
and the flags. Whatever needs you comes back as a short list, each item typed by the kind of
decision it is — a domain value, a fixture, a judgment — never blurred. And the loop eats its
own tail on purpose: Detective's functions are pinned by Detective, and the first work order
its planner ever produced named a function inside Wesker.

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

## Nobody can know this code

One thing is missing from that list, because it is not a limit of the tool. It is the
objection to the whole idea, and it deserves to be said in full:

> *So a model writes code nobody reads. Your gate stamps it. I ship it. You haven't made code
> knowable — you've made not-knowing safe. Nobody understands what is running anymore, and you
> have built the machine that lets them stop feeling bad about it.*

That objection has a distinguished pedigree. For nearly three decades MIT taught its
introductory computer science from *Structure and Interpretation of Computer Programs*, a book
whose premise is that one person can understand a system all the way down — every abstraction
they built, every layer beneath it, no magic anywhere. Around 2008 Gerald Sussman, one of its
authors, retired the course, and his reason was the objection above, stated a decade early.
Engineers no longer built systems from parts they understood. They assembled libraries they
had not written and could not read, and learned them by poking. The book's premise, he said,
no longer described the field.

He was right. He was also right in 1985, and the two only collide if knowing code means
knowing its characters — which it never did. A student who knew their program knew what it was
for and how it was put together; the Scheme was the carrier, and typing it was the price of
the idea, not the idea. What was actually lost by 2008 was the check. You could no longer read
the output and see that it still said what you meant.

A spell-checker replaces your words with text a machine wrote, and you own the meaning exactly
as before — more, if anything, since the mechanics stopped competing for your attention. What
makes that ownership real rather than a comfort is that you can read the corrected sentence.
For code, that is the part that died, and it is the part the gate restores without restoring
the reading. The contract is your intent, written as tests. The proof that the characters are
faithful to it is the machine's, and where they are not, the distinguishing input is named.
*I did not type this, and I know it* — and the second half is a proof, not a hope.

The book's preface says programs must be written for people to read, and only incidentally for
machines to execute. In a year when nobody reads the code, that sentence looks like an epitaph.
It is the ceiling theorem, forty years early: the part of a program that ever needed a human
reader is the part that says what it is for, and that part is still read, by the person who
wrote the tests. The assembly line did not make the book obsolete. It removed everything from
the craft except the part the book was written about — where to draw the barrier, when a layer
earns its keep, what the thing is for — and the field had to lose the typing to notice.

---

## Run it

```bash
uv add detective-spec          # or: uv pip install detective-spec
detective diagnose path/to/file.py::function     # start here — writes nothing
```

Installs as `detective-spec`, imports as `Detective`, runs as `detective`. Every command ends
by naming the next one, and that is not a convenience. The theorem reserved half the work —
the half about what the code is for — for whoever holds the intent, and this surface is where
that half gets done: the tool says what it measured and what it could not, you answer with an
input, a flag, a fence, and the suite that results was written by neither of you alone.

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
theorems — the ceiling, the boundary between effect and meaning, and the rest — live in
[`docs/theory/`](./docs/theory/), in full academic dress.

---

*Wesker asks the question by breaking things. Detective writes down what can be known, and
files the rest upward. Uroboros asks it of everything, forever, itself included.*

*MIT — Rohan Vinaik.*
