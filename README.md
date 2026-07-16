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

---

## For agents — the MCP surface

```bash
uv pip install 'detective-spec[mcp]'   # then run: detective-mcp   (stdio)
```

Five tools — `diagnose`, `converge`, `decompose`, `audit`, `deep_context` — over the same library the CLI uses. Every response ends in exactly one of `DO THIS:` (a literal next call), `STOP.` (a verdict), or `DONE:`. There is no score in the default view; the numbers are real and they are behind `deep_context`, because a ratio is an invitation to grind and the remaining work is not the caller's to compute.

**Three things a first-time caller needs to know, and they are all about the first run.**

**`project_root` is required, and must be absolute.** There is no default, deliberately. A stdio server's cwd is *wherever the client launched it*, fixed for the life of the process — it is not "the project", and it does not follow you to another repo. The verdict cache lives at `<project_root>/.detective/`, so a wrong root does not fail loudly; it quietly gets its own cache file and is **cold on every call, forever**.

**The first run on a large suite takes minutes.** Before it can answer anything, the engine traces the target's suite once — that is the measurement everything else rests on. On a 2134-test repo: **486s cold, 3.6s warm.**

*"Warm" means one exact question, not one repo.* What persists to `.detective/verdict_cache.json` is the finished profile of **one function under one set of budgets** — that is what returns in 3.6s. The suite **trace** is not persisted at all: it lives in memory for the length of one pytest session, and every tool call opens its own. So a second question — a different function, or the same function under different budgets — is a cache **miss** and re-pays the whole trace. Cold-vs-warm is per `(function, budgets)`, not per repo, and the cost falls on whoever asks the new question first.

Two consequences worth planning around:

- **Warm from a terminal deliberately, not as a fallback.** A CLI run and a tool call that agree on budgets produce the *same* cache key, so the CLI genuinely warms the MCP. Ask the question you actually want answered, once, where a long run is cheap to watch — then call the tool.
- **Batch on the CLI when you have many functions.** One CLI process profiling several functions traces the suite once and reuses it for all of them. The MCP cannot do this: one tool call is one session, so N functions cost N traces. The trace amortises across functions *within a process*, and a tool call is a process's worth of one function.

**If the tool call dies, it is almost certainly not a timeout.** `MCP_TOOL_TIMEOUT` defaults to ~28 hours and `CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT` to 30 minutes for stdio — raising them fixes nothing, and the 60-second figure you may have seen applies to *network* MCP servers, not this one. Detective needs **Wesker >= 0.6.2**: below it, running pytest in-process wrote pytest's own progress output onto file descriptor 1 — which for a stdio server *is* the JSON-RPC channel — so the client read `.{"jsonrpc":…`, failed to parse it, and closed the connection. The server vanished mid-session with no traceback, because nothing had crashed.

If you are on an older Wesker and cannot upgrade, warm the cache from a terminal once and the MCP call is then fast enough to survive:

```bash
detective diagnose path/to/file.py::function     # once, in a terminal
```

**The knobs the responses mention are on the tools.** When a response says tests were CUT and their coverage is under-counted, pass **`trace_session_budget=0`** (0 = unbounded). Real parameters on every tool, not something you have to go to the CLI for.

**There are TWO budgets, and the SESSION one is almost always what cut you.** `trace_budget` caps each *individual* test's traced pass; `trace_session_budget` caps the *whole* pass. A suite whose total trace outruns the session cap loses every test after it, however generous the per-test cap is — so reaching for `trace_budget` alone is the natural move and it changes nothing. Measured on Regenesis: `(50, 300)` and `(∞, 300)` cut an identical 152 tests. Raise the session one first; raise both to be sure.

**Both budgets are WALL-CLOCK, and the work is CPU-bound.** So they do not measure the suite — they measure the suite *on this machine, under this load*. The same repo traces clean on an idle box and gets cut on a busy one, and whether you were cut is not a property of your code. Two things follow. Don't read a cut count as a fact about the suite; it is a fact about the afternoon. And **no default can be "correct"** — a busy enough machine cuts at any finite value. The budget exists to stop a pathological hang, not to certify a measurement. When the answer has to be exact — certifying a function, trusting a pinned count — pass `0` and take the wall-clock hit; that is the only setting that is a statement about your code.

**Take a CUT warning seriously — it is not cosmetic.** A cut test's line coverage is under-counted, so the tests that *do* pin a behaviour cannot be credited with pinning it, and the report says "nothing distinguishes this" about behaviour the suite already covers. Measured on Regenesis: under the old 300s default, `greedy_coverage` reported **0 of 45 behaviours pinned**; unbounded, the truth is **22 of 45**. Acting on the cut number means asking `converge` to write tests for behaviour that is already specified. The report says *"this is a measurement limit, not a finding — do not act on it as one"*, and it means it: re-measure, then act.

---

[ARCHITECTURE.md](./ARCHITECTURE.md) documents the module layout, the full per-command reference, the performance and memory layers, and a symptom→cause debug map.

---

MIT — Rohan Vinaik

Built on [Wesker](https://github.com/rohanvinaik/Wesker) — mutation testing at CI speed, with a provably optimal test budget.
