# Detective

**Find out what a Python function actually does — then change it, with a proof that behavior survived.**

<p align="center">
  <a href="https://github.com/rohanvinaik/Detective/actions/workflows/ci.yml"><img src="https://github.com/rohanvinaik/Detective/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-3367d6.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-3367d6.svg" alt="Python 3.11+"></a>
</p>

`Deterministic · No LLM · Applies nothing it cannot prove`

A passing test suite tells you your code runs. It does not tell you what your code *computes*, and it does not tell you whether you can change it.

Detective answers both, one function at a time. Point it at a function and it maps every behavioral distinction the function makes, writes the minimal suite that pins them, and — once that suite exists — refactors the function and applies the change only if the suite proves behavior survived.

---

## What it sees

Your suite is green. Here is what it does not require your code to do:

```
$ detective converge stats.py::anomaly_score

  score 0% → 73% (27/37 behaviors pinned) · 4 tests written

  4 behaviors nothing distinguishes — each with the input that would:

    - if not values or window <= 0:    + if not values or window < 0:
        ↳ distinguish at the boundary — supply an input where window == 0

    - if deviation > peak:             + if deviation >= peak:
        ↳ distinguish at the boundary — supply an input where deviation == peak

    - if score > 1.0:                  + if score >= 1.0:
        ↳ distinguish at the boundary — supply an input where score == 1.0

    - return round(score, 4)           + return round(4, score)
```

Each line is a real edit to your function that **every test still passes**. The last one reverses the arguments to `round()` and nothing notices.

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

Detective wrote the suite, ran it against the original, rewrote the function, ran it again, and kept the change **only because every test still passed**. Had one failed, it would have reverted the file and told you which behavior moved.

---

## Run it

```bash
uv add detective-spec          # or: uv pip install detective-spec
```

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

## Why a suite lets you refactor

Mutation testing measures which *behaviors* your tests require: change the code, see whether a test complains. Every alteration that slips through silently is a behavior nothing constrains. Detective runs on [Wesker](https://github.com/rohanvinaik/Wesker), which makes that measurement fast enough to do per-function, per-command.

The claim Detective rests on is narrow and mechanical:

> **A suite that kills every killable mutant of a function is that function's behavioral contract.** A rewrite that keeps it green preserved the behavior the contract pins.

That is why `decompose` writes the suite first. The suite is not the product. It is the receipt.

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

Without `--apply`, nothing is ever written: extractions are shown, never applied.

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
