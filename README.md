# Detective

**Refactor a Python function and prove you didn't change it.**

<p align="center">
  <a href="https://github.com/rohanvinaik/Detective/actions/workflows/ci.yml"><img src="https://github.com/rohanvinaik/Detective/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/detective-spec/"><img src="https://img.shields.io/pypi/v/detective-spec.svg?color=3367d6" alt="PyPI"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-3367d6.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-3367d6.svg" alt="Python 3.11+"></a>
</p>

`Deterministic · No LLM · Applies nothing it cannot prove`

Your test suite is green. Detective swapped the arguments to a `round()` call in your code — `round(score, 4)` became `round(4, score)` — and the suite is still green:

```diff
- return round(score, 4)
+ return round(4, score)      # every test you wrote still passes
```

A real edit to your function, waved through. That gap is where every refactor you have ever shipped placed its bet.

---

## Green is not proof

A passing test proves your code *can* return the right answer once. It never proves your code returns *only* right answers — and no amount of testing closes the difference, because it is not a difference of degree.

The smallest function there is shows why. `assert add(1, 1) == 2` passes — and so does `3*a - b`, and so does `a*b + 1`, and so do infinitely many functions that are not addition. There is always another curve through a handful of points; every example you add leaves infinitely many standing. Three good cases feel like proof and are not. Your suite is not a contract anyway — nobody wrote it to be one. It accumulated: a regression here, a bug report there, the happy path from the afternoon the function was born. It is a residue, and you are about to stake a rewrite on it.

You do not close that gap by writing more examples. You close it by killing the degrees of freedom that matter. Swap `add`'s `+` for a `-`, and every non-trivial input separates addition from its impostors at once; forbid the degenerate `0 + 0 = 0`, and nothing trivial can hide in the gap. Two moves, and addition is pinned — for every input, provably, rather than "probably, after forty cases."

Detective does that for your function. It reads the operators the code actually runs, takes the tests you actually wrote, and works out what it would take to pin the behavior those two things already imply — then writes it. It is not chasing a Grand Truth about what your function *should* do; your suite already decided what it does. A green test is the grounded fact, the initial value, the frictionless sphere a real answer is allowed to rest on — and Detective makes that decision *true*, complete and minimal and provable, where it was merely "good enough."

> **A suite that kills every killable mutant of a function is that function's behavioral contract.** A rewrite that leaves it green preserved the behavior the contract pins.

The suite is not the product. It is the receipt.

---

## See it, pin it, prove it

**`diagnose`** reads a function and tells you what your tests leave unpinned, then names the one thing to run next. It writes nothing.

**`converge`** writes the smallest pytest suite that pins the function, and stops exactly where your inputs run out — naming what it could not reach, with the input that would:

```
$ detective converge stats.py::anomaly_score

  0% → 73% (27/37 behaviors pinned) · 4 tests written
  4 behaviors nothing distinguishes — each with the input that would:

    return round(score, 4)   →   round(4, score)
    if deviation > peak:      →   >=     supply an input where deviation == peak
    if score > 1.0:           →   >=     supply an input where score == 1.0
```

Not every kill is worth the same, and Detective is the tool that says so. A test catches a mutant two ways: it *asserts* the return value is wrong, or it merely *crashes*. Only the first pins what the function computes; a crash proves the code ran differently and nothing more — and everywhere else the two vanish into one percentage. So Detective counts assertion kills as specified behavior and reports the crashes separately, against its own score:

```
  of the pinned: 18 pin the RETURN VALUE, 2 only prove it runs (crash)
```

That second number is behavior you hold no contract for, and Detective will not spend it to flatter itself. The rule holds throughout: a survivor it cannot distinguish is `candidate-equivalent — UNPROVEN`, never `equivalent`; an input it cannot derive is a question, never a guess. What it writes is ordinary pytest — no runtime dependency on Detective, each test carrying the warrant it was written under, each already in the minimal cover.

**`decompose --apply`** rewrites the function and keeps the change only when that suite says the behavior held:

```
$ detective decompose stats.py::anomaly_score --apply

  ▸ proving: converging the target to a mutation-complete suite…
  ▸ trialling: _compute_deviation(threshold, values, window) -> score
  ▸ PROVEN — behavior preserved
  ✓ APPLIED (specified behavior preserved, auto)
```

`--apply` is a gate, not a hope: it converges a proof suite, runs it against the untouched function for a baseline, trial-writes one extraction, re-runs, and reverts unless the result stays green. A red baseline yields no proof, and nothing reaches your source that the re-run did not clear. Three outcomes, never blurred — **`✓ APPLIED`** (green before and after; your file is rewritten), **`rejected`** (a test caught the rewrite; your file is untouched), **`unproven`** (no complete suite to prove against yet; your file is untouched). Automatic out to the edge of what your tests specify; past that edge, it stops and asks.

---

## Why it holds

Under the mutation profile, two functions are the same when they draw the same distinctions — kill the same mutants, survive the same ones:

$$f \equiv g \iff \operatorname{kills}(f) = \operatorname{kills}(g)$$

Once behavior is pinned this tightly, the form stops mattering — slice the function into sashimi if you like, rewrite it in Comic Sans, have it print the 95 Theses on the way out; if it kills the same mutants, it is the same function. `x + y` and `(3x + 3y) / 3` are one and the same, provably. That equivalence is the ground under `decompose`, and it is why the suite is written *first*: it is the thing being proved against.

It is also why this is fast. Traditional mutation testing is slow because it chases correctness in general, across a whole codebase. Detective asks a decidable question — *does this function still do what your tests already say it does?* — and answers it per function, per command, in seconds. The engine underneath is [Wesker](https://github.com/rohanvinaik/Wesker).

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

When a parameter carries meaning the code does not hold — a plan name, a lookup key, a domain object — Detective refuses to guess it and shows the shape it needs. Hand it one real call (`--input "([1.0, 2.0, 10.0, 2.0], 4, 1.0)"`) and it takes over, remembering your example. A low number beside a residual is a question, not a failure.

---

## Where it stops

One function at a time, deterministic, narrow on purpose.

- **It preserves behavior, not correctness.** If the original was wrong, the rewrite is wrong the same way — provably. Detective does not know what your code is *for*.
- **It will not invent a domain value.** When a parameter's meaning is not in the code, you supply one example; it asks rather than guessing.
- **A search is not a proof of equivalence.** Undistinguishable survivors stay `UNPROVEN`; `flag` records a human judgment that a later distinguishing input overrides.
- **One function, not a repo.** There is no `detective src/`.

Detective was pointed at the engine it runs on. It found one of that engine's own functions unspecifiable — the return value was a set of `id()`s, different every run, so no assertion could ever hold. It declined to write the test. It was right, and the function was changed.

A tool that will say that about its author's code will say anything.

---

For agents: `uv pip install 'detective-spec[mcp]'` exposes the same library over MCP (`detective-mcp`, six tools), and every reply ends in one next call rather than a score. The one thing to plan around: `project_root` must be absolute, and the first run on a large suite traces it once — minutes cold, seconds warm, per exact question rather than per repo. The trace budgets, the cold/warm cache, and the full command reference live in [ARCHITECTURE.md](./ARCHITECTURE.md).

MIT — Rohan Vinaik. Built on [Wesker](https://github.com/rohanvinaik/Wesker) — mutation testing at CI speed, with a provably optimal test budget.
