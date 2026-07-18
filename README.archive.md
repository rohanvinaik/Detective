# Detective

**Refactor a Python function and prove you didn't change it.**

<p align="center">
  <a href="https://github.com/rohanvinaik/Detective/actions/workflows/ci.yml"><img src="https://github.com/rohanvinaik/Detective/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/detective-spec/"><img src="https://img.shields.io/pypi/v/detective-spec.svg?color=3367d6" alt="PyPI"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-3367d6.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-3367d6.svg" alt="Python 3.11+"></a>
</p>

`Deterministic · No LLM · Applies nothing it cannot prove`

Your test suite is green. Detective reversed the arguments to a `round()` call in your code — `round(score, 4)` became `round(4, score)` — and it stayed green:

```diff
- return round(score, 4)
+ return round(4, score)      # every test you wrote still passes
```

A real edit your suite waves through. Detective is the thing that doesn't.

---

## Why green is not proof

A passing test proves your code *can* return the right answer once. It never proves your code returns *only* right answers — and you cannot test your way across that gap, because it is not a gap of degree.

The simplest function there is shows why. `assert add(1, 1) == 2` passes. So does `3*a - b`. So does `a*b + 1`. So do infinitely many functions that are not addition — there is always another curve through a handful of points (ask any Taylor series), and each example you add leaves infinitely many curves standing. Three good cases feel like proof, and they are not. So *how do you actually know you have an addition function?*

Not by writing more pairs. You close the degrees of freedom that matter — one, to pin addition. Two, really. Swap that `+` for a `-`, and every non-trivial input separates addition from its impostors at once; forbid the degenerate `0 + 0 = 0`, so nothing trivial can hide in the gap. That is the whole specification — provable for every input, not "probably, after forty cases."

Detective does exactly that for your function. It reads the operators the code truly executes, takes the tests you truly wrote, and works out what it would take to pin the behavior those two things already imply — then writes it. It is not hunting a Grand Truth about what your function *ought* to do. Your suite already decided what it does: a green test is the grounded fact, the initial value, the frictionless sphere a real answer is allowed to rest on. Detective only makes that decision *true* — complete, minimal, provable — where before it was merely "good enough."

> **A suite that kills every killable mutant of a function is that function's behavioral contract.** A rewrite that leaves it green preserved the behavior the contract pins.

The suite is not the product. It is the receipt.

---

## See it · pin it · prove it

**`diagnose`** reads a function and reports what your tests leave unpinned, then names the single next move. It writes nothing.

**`converge`** synthesizes the smallest pytest suite that specifies the function, and halts at exactly the boundary your inputs can reach — naming what it could not pin, with the input that would:

```
$ detective converge stats.py::anomaly_score

  0% → 73% (27/37 behaviors pinned) · 4 tests written
  4 behaviors nothing distinguishes — each with the input that would:

    return round(score, 4)   →   round(4, score)
    if deviation > peak:      →   >=     supply an input where deviation == peak
    if score > 1.0:           →   >=     supply an input where score == 1.0
```

**`decompose --apply`** rewrites the function and keeps the change only when that suite says the behavior held:

```
$ detective decompose stats.py::anomaly_score --apply

  ▸ proving: converging the target to a mutation-complete suite…
  ▸ trialling: _compute_deviation(threshold, values, window) -> score
  ▸ PROVEN — behavior preserved
  ✓ APPLIED (specified behavior preserved, auto)
```

`--apply` is a gate. It converges a proof suite, runs it against the untouched function for a baseline, trial-writes one extraction, re-runs, and reverts unless the result stays green. A red baseline yields no proof, and nothing reaches your source that the re-run did not clear. The verdict is one of three, never blurred:

| | |
|---|---|
| **`✓ APPLIED`** | passed before and after — behavior held, your file is rewritten |
| **`rejected`** | the rewrite was tried and a test caught it — your file is untouched |
| **`unproven`** | nothing was tried; no complete suite exists yet — your file is untouched |

Automatic out to the edge of what your tests specify. Past that edge, it stops and asks.

---

## Not every kill is worth the same

A kill rate lies the way green does. A test catches a mutant by *asserting* the output is wrong, or by merely *crashing*. Only the first says what the function computes; a crash says the code ran differently and nothing more — yet both vanish into one percentage. So Detective counts assertion kills as specified behavior and reports the crashes separately, against its own score:

```
  of the pinned: 18 pin the RETURN VALUE, 2 only prove it runs (crash)
```

That second figure is behavior you hold no contract for, and Detective will not spend it to look better. The rule holds throughout: a survivor it cannot distinguish is `candidate-equivalent — UNPROVEN`, never `equivalent`; an input it cannot derive is a question, never a guess.

---

## Run it

```bash
uv add detective-spec          # or: uv pip install detective-spec
detective diagnose path/to/your_file.py::your_function   # start here — writes nothing
```

Installs as `detective-spec`, imports as `Detective`, runs as `detective` (PyPI's `detective` was taken years ago). Every command closes by naming the one thing to run next.

| Command | Writes | Answers |
|---|---|---|
| `diagnose file.py::fn` | nothing | what does this do, and what do I run next? |
| `converge file.py::fn` | test files | give me a complete, minimal suite |
| `decompose file.py::fn --apply` | your source | split it — applied only when proven behavior-preserving |
| `audit file.py::fn` | nothing | is the suite I have complete? minimal? what can I cut? |
| `regime` | config | how does this repo import and test — and can the suite even reach my file? |

When a parameter carries meaning the code does not hold — a plan name, a lookup key, a domain object — Detective refuses to guess it and shows the shape it needs instead:

```bash
detective decompose stats.py::anomaly_score --apply --input "([1.0, 2.0, 10.0, 2.0], 4, 1.0)"
```

Hand it one real call; it derives the rest and remembers your example. A low number beside a residual is a question, not a failure. What lands is ordinary pytest — no runtime dependency on Detective, every test carrying the warrant it was written under, every test already in the minimal cover. Run the generated ones with `pytest -m detective`.

---

## Where it stops

One function at a time, deterministic, narrow on purpose.

- **It preserves behavior, not correctness.** If the original was wrong, the rewrite is wrong the identical way — provably. Detective does not know what your code is *for*.
- **It will not fabricate a domain value.** Meaning that is not in the code, you supply once; it asks rather than inventing a number over a value it guessed.
- **A search is not a proof of equivalence.** Undistinguishable survivors stay `UNPROVEN`; `flag` records a human judgment that a later distinguishing input overrides.
- **A function, not a repo.** There is no `detective src/`.

Pointed at the engine it runs on, Detective found one of that engine's own functions unspecifiable — its return value was a set of `id()`s, different every run, so no assertion could ever hold. It declined to write the test. It was right, and the function changed.

A tool that will say that about its author's code will say anything.

---

## Why it holds

Under the mutation profile, two functions are the same when they draw the same distinctions — kill the same mutants, survive the same ones:

$$f \equiv g \iff \operatorname{kills}(f) = \operatorname{kills}(g)$$

Once behavior is pinned this tightly, the *form* stops mattering — slice the function into sashimi if you like, rewrite it in Comic Sans, have it print the 95 Theses on its way out; if it kills the same mutants, it is the same function. `x + y` and `(3x + 3y) / 3` are one and the same, provably, forever. That equivalence is the ground beneath `decompose`: a rewrite that leaves the suite green cannot have moved behavior, which is why the suite is written *first* — as the thing being proved against.

It is also why this is fast. Traditional mutation testing is slow because it chases correctness in general, across a whole codebase. Detective asks a decidable question — *does this function still do what your tests already say it does?* — so it runs per-function, per-command, in seconds. The engine underneath is [Wesker](https://github.com/rohanvinaik/Wesker). [ARCHITECTURE.md](./ARCHITECTURE.md) has the module map, the full command reference, and a symptom→cause debug map.

---

## For agents

```bash
uv pip install 'detective-spec[mcp]'   # then: detective-mcp   (stdio)
```

Six tools — `diagnose`, `converge`, `decompose`, `audit`, `flag`, `deep_context` — over the library the CLI drives. Every reply ends in one of `DO THIS:`, `STOP.`, or `DONE:`, and the default view carries no score, because a ratio invites grinding and the remaining work is not the caller's to compute. Two facts to plan around: `project_root` must be absolute, and the first run on a large suite spends minutes tracing it once (486s cold, 3.6s warm on a 2134-test repo — warm is per exact question, cached to `.detective/`, not per repo). [ARCHITECTURE.md](./ARCHITECTURE.md) has the budgets and the rest.

---

MIT — Rohan Vinaik

Built on [Wesker](https://github.com/rohanvinaik/Wesker) — mutation testing at CI speed, with a provably optimal test budget.
