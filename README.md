# Detective

**Refactor a Python function and prove you didn't change it.**

<p align="center">
  <a href="https://github.com/rohanvinaik/Detective/actions/workflows/ci.yml"><img src="https://github.com/rohanvinaik/Detective/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/detective-spec/"><img src="https://img.shields.io/pypi/v/detective-spec.svg?color=3367d6" alt="PyPI"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-3367d6.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-3367d6.svg" alt="Python 3.11+"></a>
</p>

`Deterministic · No LLM · Applies nothing it cannot prove`

Your suite is green. Detective reversed the arguments to a `round()` call in your code — `round(score, 4)` became `round(4, score)` — and the suite is still green:

```diff
- return round(score, 4)
+ return round(4, score)      # every test you wrote still passes
```

That is a real change to what your function computes, and nothing you wrote noticed. Every refactor you have ever shipped placed its bet in that gap.

---

## Green is not proof

A passing test proves your code returned the right answer once. It does not prove it returns *only* right answers, and no number of examples closes the difference.

The smallest function there is shows why. `assert add(1, 1) == 2` passes — and so does `3*a - b`, and so does `a*b + 1`, and so do infinitely many functions that are not addition. Every example you add leaves infinitely many curves still standing through the points. Three good cases feel like proof. They are not. And the suite was never a contract in the first place — nobody wrote it to be one. It accumulated: a regression here, a bug report there, the happy path from the afternoon the function was born. It is a residue, and you are about to stake a rewrite on it.

You do not close that gap with more examples. You close it by killing the degrees of freedom that matter. Swap the `+` in `add` for a `-`, and every non-trivial input separates addition from its impostors at once. Forbid the degenerate `0 + 0 = 0`, and nothing trivial can hide in the gap. Two moves, and addition is pinned — for every input, provably, rather than "probably, after forty cases."

Detective does that for your function. It reads the operators your code actually runs, takes the tests you already wrote, and works out the moves that pin the behavior those two things imply. Then it writes them.

> **A suite that kills every killable mutant of a function is that function's behavioral contract.** A rewrite that keeps it green preserved the behavior the contract pins.

Your tests are the oracle — the grounded fact that the code does its job at least once, the initial value the rest is solved from. Detective does not decide what your function *should* do; your suite already did. It makes that decision complete, minimal, and provable, where it was only "good enough."

The suite is not the product. It is the receipt.

---

## See it, write it, prove it

**`diagnose`** reads a function and tells you what your tests leave unpinned, then names the one thing to run next. It writes nothing.

**`converge`** writes the smallest suite that pins the function, and stops where your inputs run out — naming what it could not reach, with the input that would:

```
$ detective converge stats.py::anomaly_score

  0% → 73% (27/37 behaviors pinned) · 4 tests written

  4 behaviors nothing distinguishes — each with the input that would:
    return round(score, 4)   →  round(4, score)
    if deviation > peak:      →  >=   supply an input where deviation == peak
    if score > 1.0:           →  >=   supply an input where score == 1.0
```

Not every kill is worth the same, and Detective is the tool that says so. A test catches a mutant two ways: it *asserts* the return value is wrong, or it merely *crashes*. Only the first pins what the function computes; a crash proves the code ran differently and nothing more. Most tools blur the two into one percentage. Detective does not — it counts assertion kills as specified behavior and reports the crashes separately, against its own score:

```
  of the pinned: 18 pin the RETURN VALUE, 2 only prove it runs (crash)
```

That second number is behavior you hold no contract for, and Detective will not spend it to flatter its own score. The rule holds throughout: a survivor it cannot distinguish is `candidate-equivalent — UNPROVEN`, never `equivalent`; an input it cannot derive is a question, never a guess.

**`decompose --apply`** rewrites the function and keeps the change only if that suite proves the behavior held:

```
$ detective decompose stats.py::anomaly_score --apply

  ▸ proving: converging the target to a mutation-complete suite (the proof)…
  ▸ trialling: _compute_deviation(threshold, values, window) -> score
  ▸ PROVEN — behavior preserved: _compute_deviation
  ✓ APPLIED (specified behavior preserved, auto)
```

`--apply` is a gate, not a hope. It converges a proof suite, runs it against your untouched function for a baseline, trial-writes one extraction, re-runs, and reverts unless the result stays green. A red baseline can never produce a proof, and nothing reaches your source that the re-run did not clear. When the proof suite is not yet mutation-complete, it refuses rather than guess:

```
  ▸ unproven — no suite to prove against; proposed, not applied: _compute_deviation
  → can't PROVE preservation yet — the proof suite is not mutation-complete
  ▶ to prove + auto-apply: 30 mutant(s) the suite has not pinned — synthesis could
    not build a valid distinguishing input for this function's parameters.
      supply:  decompose 'anomaly_score' --apply --input "(<values>, <window>, <threshold>)"
```

Three outcomes, and Detective never blurs them:

| | Meaning |
|---|---|
| **`✓ APPLIED`** | The suite ran green before and after. Behavior survived. Your file is rewritten. |
| **`rejected`** | The rewrite was tried and a test caught it. Your file is untouched. |
| **`unproven`** | Nothing was tried — there is no complete suite to prove against yet. Your file is untouched. |

All three assume `--apply`. Without it, no candidate is ever trial-written: you get the proposals and your source is not touched. Detective refactors automatically out to the edge of what your tests specify. Past that edge, it stops and asks.

---

## What it writes

`converge` emits ordinary pytest. There is no runtime dependency on Detective and no custom runner:

```python
"""Auto-generated by Detective — warrant-classed tests for stats.py::anomaly_score."""

import pytest

from stats import anomaly_score


@pytest.mark.detective
@pytest.mark.parametrize("args, expected", [
        (([1.0, 2.0, 10.0, 2.0], 4, 1.0), 0.6325),
        (([1.0], 1, 2.5), 0.0),
        (([1.0, 1.0], 1, 2.5), 0.0),
])
def test_anomaly_score_golden(args, expected):
    """VALUE golden captures — pure + deterministic (3 inputs)."""
    assert anomaly_score(*args) == expected


@pytest.mark.detective
def test_anomaly_score_value_0():
    """VALUE survivor — distinguishing witness (equivalence search) (confidence 0.95)."""
    result = anomaly_score([], -1, -1.0)
    assert result == 0.0
```

Every test carries the warrant it was written under, and every test is in the minimal cover — Detective drops its *own* output when a test is redundant for both kills and lines, so what lands is the minimal suite, not the full set with a cleanup list. Run only the generated tests with `pytest -m detective`, or only yours with `pytest -m 'not detective'`.

`audit` assesses a suite you already have, and it never deletes without confirmation:

```
$ detective audit stats.py::anomaly_score

stats.py::anomaly_score: 4 existing test(s) — incomplete   [audit reads only — writes nothing]
  kills: 73.0%  |  mutant-complete=True  line-complete=False
  minimal cover: 3 test(s)  (bloat: 1 redundant)
  ✗ 2 uncovered line(s): [31, 36]
  PROPOSED removals (1, pointless for BOTH kills and lines — confirm to delete, never auto): test_anomaly_score_golden[args2-0.0]
  · 14 survivor(s) candidate-equivalent — no distinguishing input found (UNPROVEN: `flag` to confirm equivalent, or add a distinguishing input to kill)
  ▶ next: `converge` to synthesize the missing tests (WRITES test files + wires conftest)
```

---

## Why it holds

Two functions are the same when they draw the same distinctions — kill the same mutants, survive the same ones:

$$f \equiv g \iff \operatorname{kills}(f) = \operatorname{kills}(g)$$

Once behavior is pinned that tightly, the form stops mattering. Slice the function into sashimi, rewrite it in Comic Sans, have it print the 95 Theses on the way out — if it kills the same mutants, it is the same function. `x + y` and `(3x + 3y) / 3` are one and the same, provably. That equivalence is the ground `decompose` stands on, and it is why the suite is written *first*: it is the thing being proved against.

It is also why this is fast. Detective does not profile your codebase. It asks a decidable question about one function, from two things that are already static and free — the operators in its AST, and the tests you already have. There is no repo-scale artifact to build.

---

## Run it

```bash
uv add detective-spec          # or: uv pip install detective-spec
detective diagnose path/to/your_file.py::your_function   # start here — writes nothing
```

It installs as `detective-spec`, imports as `Detective`, and runs as `detective` — PyPI's `detective` was taken years ago. Every command closes by naming the one thing to run next.

| Command | Writes | Answers |
|---|---|---|
| `diagnose file.py::fn` | nothing | what does this do, and what do I run next? |
| `converge file.py::fn` | test files | give me a complete, minimal suite |
| `decompose file.py::fn --apply` | your source | split it — applied only when proven behavior-preserving |
| `audit file.py::fn` | nothing | is the suite I have complete? minimal? what can I cut? |
| `regime` | config | how does this repo import and test — and can the suite even reach my file? |

When a parameter carries meaning the code does not hold — a plan name, a lookup key, a domain object — Detective will not guess it. It shows the shape it needs; you hand it one real call (`--input "([1.0, 2.0, 10.0], 4, 1.0)"`) and it remembers your example (`.detective/inputs.json`), so every later command on that function already has it. A low number beside a residual is a question, not a failure.

---

## Reference

```bash
detective diagnose  file.py::fn                  # what it does, and the one thing to run next
detective converge  file.py::fn [--fast]         # greedy (1−1/e)-optimal subset per pass
detective decompose file.py::fn [--apply]        # without --apply: propose only
detective audit     file.py::fn [--remove]       # confirm deletion of pointless tests
detective flag      file.py::fn MUTANT_ID        # record: this survivor is truly equivalent
detective purge                                  # delete regeneratable analysis cruft
```

`--json` on any command emits the full result object. Generated tests land in `tests/test_<fn>_synth.py` with a wired `conftest.py`. In CI:

```yaml
- name: The critical path stays specified
  run: |
    uv pip install detective-spec
    detective audit src/pricing.py::compute_invoice --json > audit.json
```

---

## Where it stops

One function at a time, deterministic, narrow on purpose.

- **It preserves behavior, not correctness.** A proof says your rewrite does what the original did. If the original was wrong, the rewrite is wrong the same way — provably. Detective does not know what your code is *for*.
- **It will not invent a domain value.** When a parameter's meaning is not in the code, you supply one example; it asks rather than guessing, instead of reporting a confident number over a value it made up.
- **A search is not a proof of equivalence.** A survivor nothing could distinguish stays `candidate-equivalent — UNPROVEN`, never `equivalent`; `flag` records a human judgment that a later distinguishing input overrides.
- **One function, not a repo.** There is no `detective src/`.
- **Python 3.11+.**

Detective was pointed at the engine it runs on. It found one of that engine's own functions unspecifiable — the return value was a set of `id()`s, different every run, so no assertion could ever hold. It declined to write the test. It was right, and the function was changed.

A tool that will say that about its author's code will say anything.

---

## For agents — the MCP surface

```bash
uv pip install 'detective-spec[mcp]'   # then run: detective-mcp   (stdio)
```

Five tools — `diagnose`, `converge`, `decompose`, `audit`, `deep_context` — over the same library the CLI uses. Every response ends in one of `DO THIS:` (a literal next call), `STOP.` (a verdict), or `DONE:`. The score is not in the default view; it sits behind `deep_context`, because a ratio is an invitation to grind. **`project_root` is required and must be absolute** — a stdio server's cwd is wherever the client launched it, not the project, and a wrong root does not fail loudly; it quietly gets its own cache and stays cold. The first run traces the suite once (on a 2134-test repo, **486s cold, 3.6s warm**); warm is per `(function, budgets)`, not per repo, so seed it from a terminal with the exact question you want.

**The budgets are the one thing that will surprise you.** `trace_session_budget` caps the whole trace pass and is almost always what cut you — raising the per-test `trace_budget` alone changes nothing. Both are wall-clock against CPU-bound work, so no default is "correct," and a **CUT** warning is a measurement limit, not a finding: on Regenesis, the old default reported 0 of 45 behaviors pinned where the truth was 22 of 45. When an answer must be exact, pass `trace_session_budget=0` and take the wall-clock hit.

**If a call dies, it is not a timeout.** Detective needs **Wesker >= 0.6.2**; below it, in-process pytest wrote its progress onto file descriptor 1 — the stdio server's JSON-RPC channel — and the client closed the connection with no traceback. Warm the cache from a terminal once and the call survives. The full budget reference, the module layout, and a symptom→cause debug map live in [ARCHITECTURE.md](./ARCHITECTURE.md).

---

MIT — Rohan Vinaik. One function at a time, deterministic, and provably behavior-preserving — powered by [Wesker](https://github.com/rohanvinaik/Wesker).
