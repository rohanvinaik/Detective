# Detective

**Point Detective at a function and it writes the contract: every behaviour that function has, pinned by a test that fails the moment the behaviour changes — plus the short list of decisions no machine can make for you, handed back pre-typed.**

<p align="center">
  <a href="https://github.com/rohanvinaik/Detective/actions/workflows/ci.yml"><img src="https://github.com/rohanvinaik/Detective/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/detective-spec/"><img src="https://img.shields.io/pypi/v/detective-spec.svg?color=3367d6" alt="PyPI"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-3367d6.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-3367d6.svg" alt="Python 3.11+"></a>
</p>

`Deterministic · No LLM · Applies nothing it cannot prove`

Writing code is treated as a craft. Taste, structure, efficiency, verification, specification: each is held to be a judgment call, made well by an author with enough experience to make it well. Competent engineers do make them well, at the speed of a person thinking and typing. A coding agent produces orders of magnitude more code, most of it good, and periodically makes an extremely stupid mistake or loses the plot entirely.

Detective is the claim that most of that list was never judgment. What a function does is knowable — exactly, mechanically, to a boundary that can be stated and proved. Whether it is *well made* is not provable, but it is measurable, and measurable is enough to act on. What survives both is small, nameable, and yours.

Name that residue precisely and you have something the field has not had: a contract for automating the writing of code. Not the kind where a model writes something and you hope. The kind where what comes out the far end is complete against every behavioural question the code raises, and the questions it could not answer are sitting at the top of the report with your name on them.

---

## What a passing test establishes

Ask a model for a function that takes `[1,1]` and returns `[2]`. That is addition, obviously. The model can instead write something that scans its input for a `1` token, or for the string `ONE`, and emits `2` when it finds one. The request is satisfied exactly. You would never find out without reading every line it generated, which is the work you were trying to avoid.

The hole that permits this is older than language models, and it catches people just as cleanly. Between any set of input-output pairs a function can express there are infinitely many functions expressing the same contract. `[1,1] → [2]` comes from `x + y`. It also comes from `3x - y`, and from `x² + y`, and from an unbounded supply of others. A finite set of examples does not identify the code that passed them. It never did.

Addition is the trivial case. The failures that ship live where common sense runs out. Give free shipping to a customer who spends fifty dollars: one comparison, until you ask whether exactly fifty qualifies, and then whether a sale that drops the total below the threshold still qualifies, which depends on whether shipping is priced before or after the discount, and whether a sale landing exactly on the cutoff counts, and whether tax is included, and whether it is included for a state that charges none, and whether any of it survives an address outside the country. Each detail is trivially forgettable. Each is a place where the function quietly means something other than what was intended.

Writing more tests is the obvious answer. It is also exhausting, and every test is one more example — so it does not close the hole it was written to close.

## Mutation is the mechanism

Take `x + y` and flip the `+` to a `-`. That produces a function that is similar and wrong, and any input on which the two disagree is proof your tests can tell them apart. Do that for every operator in the function, treat the degenerate cases as checked exceptions rather than assumptions, and nothing can change what the code computes without a test going red.

This is mutation testing, and it has been in the literature for fifty years. Mutate the operators and you generate a population of near-misses: functions that are almost the one you wrote, each wrong in exactly one way, each showing precisely where the code is unspecified. It is the most rigorous mechanical check of what code actually does. The mechanism is formal, not a matter of taste. And it is a strict superset of MC/DC, the standard behind aviation-grade software, because killing a flipped-condition mutant demands an input on which that condition independently changes the result — which is the MC/DC obligation, restated.

Some mutants are genuinely equivalent and nothing kills them. Change a name field from `"Alice"` to `"Bob"` and the output is unchanged; that match is fine, and it means nothing is wrong. Every other survivor is a live mechanism by which a bug enters the code.

A function clear of everything but the truly equivalent is **pinned**. Pinned is the mechanical form of correct: it does what it was made to do, and nothing it does can change unnoticed.

Two things kept this out of practice. Mutation testing is slow, because every function must be broken every way it can break. And a failing score is not actionable. *Your code is unspecified.* Thank you. Now what.

## Wesker makes it cheap

[Wesker](https://github.com/rohanvinaik/Wesker) reasons about the function before generating anything. An addition has no boolean to flip, so no boolean mutant exists, and producing one is waste. What matters is the set of mutants that bear on the function actually written; eliminating the rest removes roughly half the space before a single test runs. That elimination is the Monty Hall filter.

The rest is mechanical. Mutants are compiled from the AST and evaluated in memory — no subprocess, no rewriting files on disk — so producing a mutant and running the tests that could kill it is one cheap operation instead of a build. One mutant per behavioural question, never forty phrasings of the same one, with the selection bound machine-checked in Lean.

## Detective decides what it means

Wesker produces the mutant regime. Detective works out what it implies.

What does it take for this behaviour to be unpinned. What would pin it. Is the answer already implicit in the code and merely never written down. Where the answer is knowable, Detective derives the distinguishing input, writes the test, and confirms the test kills the mutant it was written for. Where it is not knowable, it works out what *would* make it known and asks for exactly that, pre-typed, so the reply is a paste rather than an afternoon.

Here is that shipping rule, written the way anyone would write it, in a repository with no tests in it at all:

```python
def shipping_fee(subtotal: float, discount: float, threshold: float) -> float:
    net = subtotal - discount
    if net > threshold:
        return 0.0
    return 5.99
```

```
$ detective converge 'shipping.py::shipping_fee'

  ▸ no existing test reaches this target — synthesizing its suite from scratch…
  ▸ pass 0: 17 value-survivor(s) — synthesizing killing tests…
  ▸ witness pass: +2 distinguishing kill test(s) auto-written
  ▸ reproducibility confirmed — the certificate rests on the isolated observation

shipping.py::shipping_fee — converge · 17 behaviours · 17 pinned

  ✓ wrote              3 test(s) → tests/detective/test_shipping_shipping_fee_f061610ee4_synth.py

FINAL shipping.py::shipping_fee: ✓ COMPLETE (operator universe) · 17/17 killed
```

Seventeen behavioural questions in four lines of code, and all seventeen closed by three tests. Two of them:

```python
@pytest.mark.detective
def test_shipping_fee_value_1():
    """VALUE survivor — distinguishing witness (equivalence search) (confidence 0.95)."""
    result = shipping_fee(subtotal=0.0, discount=0.0, threshold=0.0)
    assert result == 5.99


@pytest.mark.detective
def test_shipping_fee_value_2():
    """VALUE survivor — distinguishing witness (equivalence search) (confidence 0.95)."""
    result = shipping_fee(subtotal=-1.0, discount=-1.0, threshold=-1.0)
    assert result == 0.0
```

Both calls produce the same discounted total. They differ only in where the threshold sits relative to it: level with it in the first, below it in the second. One pays. One ships free. That is the question about *exactly fifty dollars* — three clauses deep in the cascade above, the kind that reaches production — found mechanically, isolated, and now permanent.

The numbers look nothing like a shopping cart, and that is the point. These are not example purchases. Each one is the input that separates the function you wrote from a function you did not.

On real code the leftovers are the interesting part, and there are three kinds. They are never blurred together, because the right response to each is different:

```
  ✗ real gaps          2 killable mutant(s) no test kills
  · unproven-equiv     2 survivor(s) — the search found no distinguishing input
  · crash-only-equiv   1 survivor(s) — detected by crash; no value pins them
```

A real gap gets a test. A survivor that no input distinguishes is left alone and labelled, because whether it is truly equivalent is undecidable and the engine will not claim what it cannot establish. A mutant caught by a crash proves the code ran differently and proves nothing about what it computes, so it never counts toward specification. The formal argument for where that line falls is in this repository: a machine-checked account of what a mutation regime can determine about a function, and what must come from the author instead.

Where behaviour cannot be reached at all, Detective declines and names the remedy. A function that reads the wall clock is refused outright — a test pinned to the current time is green today and a lie by Tuesday. A parameter whose meaning lives in your head is requested once, then kept. And when the run itself cannot be trusted, the numbers are withheld rather than reported:

```
STOP:  one or more mutants were installed but no test ever called them, so their survival
       measures REACH, not specification — the namespace holds the mutant while the caller
       holds the original; route a test through the patched name, or pin the caller
```

Every command ends by naming the next one. Following the printed block is the entire protocol, and it requires knowing nothing about mutation testing.

## The half that really is judgment

Whether code is *good* genuinely is subjective. SICP structure, performance, length, type coverage: all legitimate, several in direct conflict. Detective treats each quality metric as a lossy lens on one underlying truth. Where independent lenses converge on the same improvement, the finding is reported with what to do about it. Where a single lens objects alone, the verdict is `AMBIGUOUS` and it goes to a person. The lenses are never averaged. A weighted sum of incommensurable axes is how code-quality scores lie.

Pointed at its own repository, the planner flagged 66 functions, funded 5, deferred 7 on budget, and recorded 54 as having no safe recipe yet.

## Where it stops

- **It preserves behaviour, not intent.** If the function was built to do the wrong thing, the contract pins the wrong thing exactly. What code is *for* is not in the code, and the theory here proves that rather than assuming it.
- **The questions are the ones the policy asks.** Every verdict is measured against a versioned operator universe whose identifier is written into the receipt and whose gaps are documented. `✓ COMPLETE (operator universe)` means precisely that and nothing wider.
- **Pure code pins fully. Impure code is declined with the remedy named** — a clock to freeze, a fixture to supply — never guessed at.
- **A failed search proves nothing.** An undistinguished survivor stays `UNPROVEN`. A `flag` records your judgment, and a later distinguishing input overrides it.
- **One function at a time.** There is no repository-scale mutation profile. Whole trees are [Uroboros](https://github.com/rohanvinaik/Uroboros)'s problem.

Pointed at the engine it runs on, Detective found a function returning a set of memory addresses — different on every run, impossible to assert against. It declined to write the test and said why. It was right. The function was changed.

## Run it

```bash
uv add detective-spec          # or: uv pip install detective-spec
detective --help               # its first block names where to start
```

| Command | Writes | Answers |
|---|---|---|
| `regime` | config | can a verdict here be trusted at all? **new repo starts here** |
| `diagnose file.py::fn` | nothing | what does this do, and what runs next? |
| `audit file.py::fn [--check]` | nothing | what does the existing suite actually pin? (CI-gateable) |
| `converge file.py::fn` | test files | write the contract |
| `plan` / `parsimony` / `survey` | nothing | the judgment half — advisory, never a gate |
| `decompose file.py::fn --apply` | your source | split it, only where behaviour is proven preserved |
| `receipt` / `verify-rewrite` | ledger | hold any rewrite to the contract |
| `flag file.py::fn ID [--fence]` | ledger | record an equivalence, or author a must-not |
| `doctor [file.py::fn]` | nothing | why is there no verdict, and is the problem me? |

Exit codes are epistemics rather than pass/fail: `0` clean · `1` a measured gap or a refusal · `2` your world is wrong, fix that and not the code · `3` the measurement cannot be trusted, re-run. Machine consumers get the same verdicts as JSON; agents get an MCP surface (`detective-spec[mcp]`). Operational reference lives in [ARCHITECTURE.md](./ARCHITECTURE.md), the theory in [`docs/theory/`](./docs/theory/), in full academic dress.

## What the contract is for

There is a quantity underneath all of this, and it is older than the tool:

$$\sigma(P,\mu)=\min\{\,|T| \;:\; T \text{ kills every non-equivalent } m \in \mathrm{Mut}_\mu(P)\,\}$$

The minimum evidence required to identify a computation against the alternatives you admit. It has a name in learning theory and a proof. Until now it had no instrument.

Detective computes it at a terminal, one function at a time. What that buys is not a better test suite. It is the end of the assumption that knowing what your code does requires someone experienced enough to guess well.

Coding stops being a craft. It becomes an assembly line.

---

*Wesker asks the question by breaking things. Detective writes down what can be known, and files the rest upward.*

*MIT — Rohan Vinaik.*
