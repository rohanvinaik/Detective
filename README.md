# Detective

**Refactor a Python function and prove you didn't change it.**

<p align="center">
  <a href="https://github.com/rohanvinaik/Detective/actions/workflows/ci.yml"><img src="https://github.com/rohanvinaik/Detective/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-3367d6.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-3367d6.svg" alt="Python 3.11+"></a>
</p>

`Deterministic · No LLM · Applies nothing it cannot prove`

Every refactor is a bet. You read the function, you believe you understand it, you change it, the suite goes green, and you ship. The green is not evidence. It is the absence of evidence, and it looks exactly the same.

The bet is unavoidable because **your tests are not a contract**. Nobody wrote them to be one. They accumulated — a regression here, a bug report there, a happy path from the afternoon the function was born. What they collectively require of your code is not a thing anyone decided. It is a residue. And you are about to bet a refactor on it.

Detective's claim is narrow and mechanical:

> **A suite that kills every killable mutant of a function is that function's behavioral contract.**
> A rewrite that keeps it green preserved the behavior the contract pins.

So it builds the contract you never wrote. It enumerates every behavioral distinction the function makes, synthesizes the minimal suite that pins each one, and then rewrites the function — applying the change only if that suite proves the behavior survived.

The suite is not the product. It is the receipt.

---

## What it sees

Your suite is green. Here is what it does not require your code to do:

```
$ detective converge stats.py::anomaly_score

  score 0% → 73% (27/37 behaviors pinned) · 4 tests written

  4 behaviors nothing distinguishes — each with the input that would:

    - return round(score, 4)           + return round(4, score)

    - if not values or window <= 0:    + if not values or window < 0:
        ↳ distinguish at the boundary — supply an input where window == 0

    - if deviation > peak:             + if deviation >= peak:
        ↳ distinguish at the boundary — supply an input where deviation == peak

    - if score > 1.0:                  + if score >= 1.0:
        ↳ distinguish at the boundary — supply an input where score == 1.0
```

Read the first one again. Detective reversed the arguments to `round()` — and **every test still passed**. Every line here is a real edit to your function that your suite does not notice, and each boundary case comes with the exact input that would catch it.

Line coverage cannot see any of this. It reports which lines *ran*.

---

## What it does about it

```
$ detective decompose stats.py::anomaly_score --apply

  ▸ proving: converging the target to a mutation-complete suite (the proof)…
  ▸ trialling: _compute_deviation(threshold, values, window) -> score …
  ▸ PROVEN — behavior preserved: _compute_deviation

  ✓ APPLIED (specified behavior preserved, auto)
```

```diff
  def anomaly_score(values, window, threshold):
      if not values or window <= 0:
          return 0.0
-
-     recent = values[-window:]
-     n = len(recent)
-     total = 0.0
-     for v in recent:
-         total = total + v
-     mean = total / n
-     …  25 more lines: variance, spread, peak deviation, the z-score, the clamp
-     if score > 1.0:
-         score = 1.0
-
+     score = _compute_deviation(threshold, values, window)
      return round(score, 4)
```

This is not "rewrite the AST and hope." `--apply` is a gate, and the loop behind it is:

1. **converge** the target to a mutation-complete suite — the proof
2. run that suite against the **unchanged** function — the baseline
3. **propose** extraction candidates, deterministically, from the function's structure
4. **trial-write** a candidate to disk and re-run the suite
5. keep it **only if green** — otherwise revert the file and say which behavior moved

A red baseline can never produce a proof, and nothing reaches your source that step 5 did not clear. Without `--apply`, step 4 never runs: candidates are shown and never written.

**Detective refactors automatically, but only up to the boundary of the behavior your tests actually specify.** Past that boundary it stops and asks.

---

## Run it

```bash
uv add detective-spec          # or: uv pip install detective-spec
```

Installs as `detective-spec`, imports as `Detective`, runs as `detective`. The install
name differs because PyPI's `detective` was taken years ago by an unrelated project.

<details>
<summary>From source</summary>

```bash
git clone https://github.com/rohanvinaik/Detective.git
cd Detective
uv sync
```
</details>

**Start here — this writes nothing:**

```bash
detective diagnose path/to/your_file.py::your_function
```

```
stats.py::anomaly_score  [regime B — entangled]
  37 distinct behaviors; 0 pinned by a test, 37 unpinned
  of the pinned: 0 pin the RETURN VALUE, 0 only prove it runs (crash)
  ⚠ NO tests discovered for this function — the counts above reflect ABSENT
    tests, not weak ones; run `converge` to generate them
  in plain terms:
    → 37 behavior(s) no test pins yet — run `converge` to generate tests for them
    ★ LOOK HERE FIRST — two independent signals agree this is really >1 thing:
      behaviorally entangled (regime B) AND 1 clean structural seam(s).
      `decompose` proves it's behavior-preserving and splits it.
```

Every command ends by telling you what to run next. Follow it.

### The four commands

| Command | Writes | What it answers |
|---|---|---|
| `detective diagnose file.py::fn` | nothing | What does this function actually do, and what should I run next? |
| `detective converge file.py::fn` | test files | Give me a complete, minimal suite for it. |
| `detective decompose file.py::fn --apply` | your source | Split it — applied **only** if proven behavior-preserving. |
| `detective audit file.py::fn` | nothing | Is the suite I already have complete? Minimal? What can I delete? |

Python 3.11+. Nothing to configure.

### `--input` — how you tell it what it can't know

Some parameters carry meaning that isn't in the code: a plan name, a lookup key, a valid domain object. Detective will not guess one. It stops and shows you the exact shape it needs:

```
▶ 30 residual(s) need a real input to kill/classify —
  supply --input "(<values>, <window>, <threshold>)"
```

Hand it one real call, and it takes over from there:

```bash
detective decompose stats.py::anomaly_score --apply --input "([1.0, 2.0, 10.0, 2.0], 4, 1.0)"
```

That's the whole interface. You supply what only you know; Detective derives the rest and remembers your example (`.detective/inputs.json`), so every later command on that function already has it.

If a run comes back with a low number and a residual, that's the tool asking a question, not failing. Answering it is usually the difference between `0/76` and a finished suite.

---

## The number that lies

Mutation testing measures which *behaviors* your tests require: change the code, see whether a test complains. Every alteration that slips through silently is a behavior nothing constrains. Detective runs on [Wesker](https://github.com/rohanvinaik/Wesker), which makes that measurement fast enough to do per-function, per-command.

Which would be the whole story, except that **a kill rate can lie the same way a green suite can.**

A test catches a mutant two ways. It can *assert* the return value is wrong — or it can simply *crash*. Only the first pins what your function computes. A crash proves the code ran differently. It says nothing about what the code is *for*.

The two are indistinguishable in a kill rate. A tool reporting 95% where most kills are crashes has told you almost nothing about your return values, and you cannot refactor against it — you would be betting on a contract that only ever asserted *this line executes*. That is the green suite's lie again, wearing a percentage.

So Detective counts only assertion kills as specified behavior, and reports the crashes separately, against itself:

```
  of the pinned: 18 pin the RETURN VALUE, 2 only prove it runs (crash)
```

That second number is behavior you have no contract for. Detective will not spend it to make its own score look better. It is the same discipline everywhere else in the tool: a survivor nothing could distinguish is `candidate-equivalent — UNPROVEN`, never `equivalent`; an input it cannot derive is a question, never a guess.

This is why `decompose` writes the suite *first*. Not as a courtesy. As the thing being proved against.

---

## The proof gate

`decompose` will refuse. That is the feature.

```
$ detective decompose stats.py::anomaly_score --apply

  ▸ no proof suite — nothing can be proven; extractions will be proposed only
  ▸ unproven — no suite to prove against; proposed, not applied: _compute_deviation

  → can't PROVE preservation yet — the proof suite is not mutation-complete
  ▶ to prove + auto-apply: 30 mutant(s) the suite has not pinned — synthesis could
    not build a valid distinguishing input for this function's parameters.
      supply:  decompose 'anomaly_score' --apply --input "(<values>, <window>, <threshold>)"
```

There are exactly three outcomes, and Detective never blurs them:

| | Meaning |
|---|---|
| **`✓ APPLIED`** | The suite ran green before and after. Behavior survived. Your file is rewritten. |
| **`rejected — the suite says behavior changed`** | The rewrite was tried and a test caught it. Your file is untouched. |
| **`unproven`** | Nothing was tried — there is no complete suite to prove against yet. Your file is untouched. |

All three outcomes above assume `--apply`. Without it, no candidate is ever trial-written — you get the proposals and your source is not touched.

---

## What it writes

`converge` emits ordinary pytest. No runtime dependency on Detective, no custom runner:

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

Every test carries the warrant it was written under, and every test is in the minimal cover — Detective drops its *own* output when a test is redundant for both kills and lines, so what lands is the minimal suite, not the full set plus a cleanup list.

Run only the generated tests with `pytest -m detective`, or only yours with `pytest -m 'not detective'`.

`audit` assesses a suite you already have, and never deletes without confirmation:

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

## What it does not do

Detective is one function at a time, deterministic, and narrow on purpose.

- **It preserves behavior, not correctness.** A proof says your rewrite does what the original did. If the original was wrong, the rewrite is wrong in exactly the same way — provably. Detective does not know what your code is *for*.
- **It will not invent a domain value.** If a parameter's meaning isn't in the code, you supply one example. It asks rather than guessing, instead of reporting a confident number over a value it made up.
- **Automated search does not prove equivalence.** Survivors nothing could distinguish are reported `candidate-equivalent — UNPROVEN`, never as equivalent. `detective flag` records a human judgment; a later distinguishing input overrides it.
- **One function, not a repo.** There is no `detective src/`.
- **Python 3.11+.**

Detective was pointed at the engine it runs on. It reported that one of that engine's own functions could not be specified at all — the return value was a set of `id()`s, different every run, so no assertion could ever hold. It declined to write the test. It was right, and the function was changed.

A tool that will tell you that about its author's code will tell you anything.

---

## Reference

```bash
detective diagnose  file.py::fn [--learn]        # + which categories this project leaves weak
detective converge  file.py::fn [--fast]         # greedy (1−1/e)-optimal subset per pass
detective decompose file.py::fn [--apply]        # without --apply: propose only
detective audit     file.py::fn [--remove]       # confirm deletion of pointless tests
detective flag      file.py::fn MUTANT_ID        # record: this survivor is truly equivalent
detective purge                                  # delete regeneratable analysis cruft
```

`--json` on any command emits the full result object. `--parallel` / `--serial` override the adaptive default (verdicts are identical either way). Generated tests land in `tests/test_<fn>_synth.py` with a wired `conftest.py`.

In CI:

```yaml
- name: The critical path stays specified
  run: |
    uv pip install detective-spec
    detective audit src/pricing.py::compute_invoice --json > audit.json
```

[ARCHITECTURE.md](./ARCHITECTURE.md) documents the module layout, the full per-command reference, the performance and memory layers, and a symptom→cause debug map.

---

MIT — Rohan Vinaik

Built on [Wesker](https://github.com/rohanvinaik/Wesker) — mutation testing at CI speed, with a provably optimal test budget.
